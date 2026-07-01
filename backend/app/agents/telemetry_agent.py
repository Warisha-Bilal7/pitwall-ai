from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.f1_models import Lap, PitStop, Driver
from app.agents.llm import get_llm
from app.agents.state import AgentState
import uuid
import statistics
import re


async def _get_driver_laps(session_id: uuid.UUID, driver_number: int) -> list[Lap]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Lap)
            .where(Lap.session_id == session_id, Lap.driver_number == driver_number)
            .order_by(Lap.lap_number)
        )
        return list(result.scalars().all())


async def _get_session_drivers(session_id: uuid.UUID) -> list[Driver]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Driver).where(Driver.session_id == session_id).order_by(Driver.driver_number)
        )
        return list(result.scalars().all())


async def _get_pit_stops(session_id: uuid.UUID, driver_number: int) -> list[PitStop]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(PitStop)
            .where(PitStop.session_id == session_id, PitStop.driver_number == driver_number)
            .order_by(PitStop.lap_number)
        )
        return list(result.scalars().all())

def _find_driver_numbers_in_query(query: str, drivers: list[Driver]) -> list[int]:
    """
    Returns ALL driver numbers whose surname or acronym appears in the query
    as a whole word. Uses word-boundary matching to prevent acronyms like
    'STR' matching as substrings inside driver names (e.g. 'STR' in 'Piastri').
    """
    query_lower = query.lower()
    matched = []
    for d in drivers:
        surname = d.full_name.split()[-1].lower() if d.full_name else ""
        acronym = d.name_acronym.lower() if d.name_acronym else ""
        if surname and re.search(rf"\b{re.escape(surname)}\b", query_lower):
            matched.append(d.driver_number)
        elif acronym and re.search(rf"\b{re.escape(acronym)}\b", query_lower):
            matched.append(d.driver_number)
    return matched

def _compute_pace_anomalies(laps: list[Lap]) -> dict:
    """
    Computes basic stats: fastest/slowest lap, average, and any laps that
    deviate significantly (>1.5 std dev) from the driver's median pace.
    Excludes pit-out laps since those are naturally slower.
    """
    valid = [l for l in laps if l.lap_duration and not l.is_pit_out_lap]
    if len(valid) < 3:
        return {"laps_analyzed": len(valid), "anomalies": [], "note": "Not enough clean laps to analyze."}

    durations = [l.lap_duration for l in valid]
    median = statistics.median(durations)
    stdev = statistics.stdev(durations) if len(durations) > 1 else 0

    anomalies = []
    for l in valid:
        if stdev > 0 and abs(l.lap_duration - median) > 1.5 * stdev:
            direction = "slower" if l.lap_duration > median else "faster"
            anomalies.append({
                "lap": l.lap_number,
                "duration": round(l.lap_duration, 3),
                "deviation": direction,
                "delta_from_median": round(l.lap_duration - median, 3),
            })

    fastest = min(valid, key=lambda l: l.lap_duration)
    slowest = max(valid, key=lambda l: l.lap_duration)

    return {
        "laps_analyzed": len(valid),
        "median_lap_time": round(median, 3),
        "fastest_lap": {"lap": fastest.lap_number, "duration": round(fastest.lap_duration, 3)},
        "slowest_lap": {"lap": slowest.lap_number, "duration": round(slowest.lap_duration, 3)},
        "anomalies": anomalies[:5],
    }


def _compute_pit_stop_outliers(pit_stops: list[PitStop]) -> dict:
    durations = [p.pit_duration for p in pit_stops if p.pit_duration]
    if not durations:
        return {"pit_stops": 0, "outliers": []}

    avg = sum(durations) / len(durations)
    outliers = [
        {"lap": p.lap_number, "duration": round(p.pit_duration, 1)}
        for p in pit_stops
        if p.pit_duration and abs(p.pit_duration - avg) > 3.0
    ]
    return {
        "pit_stops": len(pit_stops),
        "average_duration": round(avg, 1),
        "outliers": outliers,
    }


def _build_driver_telemetry_block(driver: Driver, laps: list[Lap], pit_stops: list[PitStop]) -> str:
    """Formats one driver's computed stats into a labelled text block for the LLM prompt."""
    pace_stats = _compute_pace_anomalies(laps)
    pit_stats = _compute_pit_stop_outliers(pit_stops)
    return (
        f"Driver: #{driver.driver_number} {driver.full_name} ({driver.team_name})\n"
        f"Pace analysis: {pace_stats}\n"
        f"Pit stop analysis: {pit_stats}"
    )


async def telemetry_agent(state: AgentState) -> dict:
    """
    LangGraph node: analyzes pace and pit stop data for all drivers mentioned
    in the query, then asks the LLM to phrase the findings as a natural-language
    answer grounded in the computed stats.

    Supports single-driver and multi-driver (comparison) queries.
    """
    session_id = uuid.UUID(state["session_id"])
    query = state["query"]

    drivers = await _get_session_drivers(session_id)
    driver_numbers = _find_driver_numbers_in_query(query, drivers)

    if not driver_numbers:
        return {
            "telemetry_output": (
                "I couldn't identify which driver you're asking about. "
                "Could you mention them by name (e.g. 'Verstappen' or 'NOR')?"
            )
        }

    # Build a stats block for each matched driver
    driver_blocks = []
    for driver_number in driver_numbers:
        driver = next(d for d in drivers if d.driver_number == driver_number)
        laps = await _get_driver_laps(session_id, driver_number)
        pit_stops = await _get_pit_stops(session_id, driver_number)
        driver_blocks.append(_build_driver_telemetry_block(driver, laps, pit_stops))

    combined_data = "\n\n".join(driver_blocks)
    is_comparison = len(driver_numbers) > 1

    if is_comparison:
        instruction = (
            "Compare these drivers directly — pace, anomalies, pit stop efficiency. "
            "Be specific with lap numbers and times. State clearly which driver had the edge "
            "and in what areas. Keep the answer to 4-6 sentences."
        )
    else:
        instruction = (
            "Answer the user's question using ONLY the data above. Be specific with lap numbers and "
            "times. If there are pace anomalies, explain what they likely mean (tyre degradation, "
            "traffic, a mistake, etc.) but be clear when you're speculating vs stating a fact from "
            "the data. Keep the answer to 3-5 sentences."
        )

    llm = get_llm(temperature=0.2)
    prompt = f"""You are a Formula 1 race engineer analyzing telemetry data.

{combined_data}

User question: "{query}"

{instruction}"""

    response = llm.invoke(prompt)
    return {"telemetry_output": response.content}