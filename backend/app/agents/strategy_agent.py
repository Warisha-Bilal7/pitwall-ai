from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.f1_models import Lap, PitStop, Driver
from app.agents.llm import get_llm
from app.agents.state import AgentState
import uuid
import re

async def _get_session_drivers(session_id: uuid.UUID) -> list[Driver]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Driver).where(Driver.session_id == session_id).order_by(Driver.driver_number)
        )
        return list(result.scalars().all())


async def _get_driver_laps(session_id: uuid.UUID, driver_number: int) -> list[Lap]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Lap)
            .where(Lap.session_id == session_id, Lap.driver_number == driver_number)
            .order_by(Lap.lap_number)
        )
        return list(result.scalars().all())


async def _get_driver_pit_stops(session_id: uuid.UUID, driver_number: int) -> list[PitStop]:
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


def _compute_stints(laps: list[Lap], pit_stops: list[PitStop]) -> list[dict]:
    """
    Splits a driver's laps into stints based on pit stop laps, and computes
    average pace per stint.
    """
    pit_laps = sorted([p.lap_number for p in pit_stops if p.lap_number])
    if not laps:
        return []

    stints = []
    stint_start = laps[0].lap_number
    boundaries = pit_laps + [laps[-1].lap_number + 1]

    for boundary in boundaries:
        stint_laps = [
            l for l in laps
            if stint_start <= l.lap_number < boundary and l.lap_duration and not l.is_pit_out_lap
        ]
        if stint_laps:
            durations = [l.lap_duration for l in stint_laps]
            stints.append({
                "stint_laps": f"{stint_laps[0].lap_number}-{stint_laps[-1].lap_number}",
                "lap_count": len(stint_laps),
                "avg_pace": round(sum(durations) / len(durations), 3),
                "first_lap_time": round(stint_laps[0].lap_duration, 3),
                "last_lap_time": round(stint_laps[-1].lap_duration, 3),
                "degradation": round(stint_laps[-1].lap_duration - stint_laps[0].lap_duration, 3),
            })
        stint_start = boundary

    return stints


def _build_driver_strategy_block(driver: Driver, laps: list[Lap], pit_stops: list[PitStop]) -> str:
    """Formats one driver's computed strategy stats into a labelled text block for the LLM prompt."""
    stints = _compute_stints(laps, pit_stops)
    pit_summary = [
        {"lap": p.lap_number, "duration": round(p.pit_duration, 1) if p.pit_duration else None}
        for p in pit_stops
    ]
    return (
        f"Driver: #{driver.driver_number} {driver.full_name} ({driver.team_name})\n"
        f"Pit stops: {pit_summary}\n"
        f"Stint breakdown: {stints}"
    )


async def strategy_agent(state: AgentState) -> dict:
    """
    LangGraph node: computes stint breakdown and pit timing for all drivers
    mentioned in the query, then asks the LLM to reason about strategy.

    Supports single-driver and multi-driver (comparison) queries.
    """
    session_id = uuid.UUID(state["session_id"])
    query = state["query"]

    drivers = await _get_session_drivers(session_id)
    driver_numbers = _find_driver_numbers_in_query(query, drivers)

    if not driver_numbers:
        return {
            "strategy_output": (
                "I couldn't identify which driver you're asking about for strategy analysis. "
                "Could you mention them by name?"
            )
        }

    # Build a strategy block for each matched driver
    driver_blocks = []
    for driver_number in driver_numbers:
        driver = next(d for d in drivers if d.driver_number == driver_number)
        laps = await _get_driver_laps(session_id, driver_number)
        pit_stops = await _get_driver_pit_stops(session_id, driver_number)
        driver_blocks.append(_build_driver_strategy_block(driver, laps, pit_stops))

    combined_data = "\n\n".join(driver_blocks)
    is_comparison = len(driver_numbers) > 1

    if is_comparison:
        instruction = (
            "Compare these drivers' strategies directly — stint lengths, tyre degradation trends, "
            "pit stop timing and duration. State clearly which driver had the better strategy "
            "and why, based only on the data above. Keep the answer to 4-6 sentences."
        )
    else:
        instruction = (
            "Discuss stint length, tyre degradation trend (positive 'degradation' value means lap "
            "times got slower across the stint), and whether the pit timing looks reasonable given "
            "the pace drop-off. Be clear about what's directly supported by the data vs. your "
            "strategic interpretation. Keep the answer to 3-5 sentences."
        )

    llm = get_llm(temperature=0.3)
    prompt = f"""You are a Formula 1 strategist analyzing race strategy.

{combined_data}

User question: "{query}"

Answer using ONLY the data above. {instruction}"""

    response = llm.invoke(prompt)
    return {"strategy_output": response.content}