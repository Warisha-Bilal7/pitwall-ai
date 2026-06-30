from sqlalchemy import select, func
from app.database import AsyncSessionLocal
from app.models.f1_models import Lap, Driver
from app.services.embeddings import search_similar_documents
from app.agents.llm import get_llm
from app.agents.state import AgentState
import uuid
import re


# ── Superlative detection ─────────────────────────────────────────────────────

SUPERLATIVE_PATTERNS = [
    r"\bfastest\b", r"\bquickest\b", r"\bslowest\b",
    r"\bbest lap\b", r"\bworst lap\b",
    r"\bmost pit stops\b", r"\bfewest pit stops\b",
    r"\bwho won\b", r"\bwho finished\b",
    r"\bhighest speed\b", r"\blowest speed\b",
    r"\bmost laps\b", r"\bfewest laps\b",
]

def _is_superlative_query(query: str) -> bool:
    q = query.lower()
    return any(re.search(p, q) for p in SUPERLATIVE_PATTERNS)


# ── SQL fast-path for precise factual lookups ─────────────────────────────────

async def _fastest_lap_lookup(session_id: uuid.UUID) -> str:
    """Returns structured text about the overall fastest lap of a session."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Lap, Driver)
            .join(Driver, (Driver.session_id == Lap.session_id) &
                          (Driver.driver_number == Lap.driver_number))
            .where(
                Lap.session_id == session_id,
                Lap.lap_duration.isnot(None),
                Lap.is_pit_out_lap == False,
            )
            .order_by(Lap.lap_duration.asc())
            .limit(5)
        )
        rows = result.all()

    if not rows:
        return "No lap time data available for this session."

    lines = ["Top 5 fastest laps in this session:"]
    for i, (lap, driver) in enumerate(rows, 1):
        lines.append(
            f"  {i}. #{driver.driver_number} {driver.full_name} ({driver.team_name}) "
            f"— Lap {lap.lap_number}: {lap.lap_duration:.3f}s"
        )
    return "\n".join(lines)


async def _most_laps_lookup(session_id: uuid.UUID) -> str:
    """Returns drivers ranked by total laps completed."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Lap.driver_number, func.count(Lap.id).label("lap_count"))
            .where(Lap.session_id == session_id)
            .group_by(Lap.driver_number)
            .order_by(func.count(Lap.id).desc())
            .limit(5)
        )
        rows = result.all()

        driver_numbers = [r[0] for r in rows]
        driver_result = await db.execute(
            select(Driver).where(
                Driver.session_id == session_id,
                Driver.driver_number.in_(driver_numbers),
            )
        )
        drivers = {d.driver_number: d for d in driver_result.scalars().all()}

    lines = ["Drivers by laps completed:"]
    for driver_number, lap_count in rows:
        d = drivers.get(driver_number)
        name = f"{d.full_name} ({d.team_name})" if d else f"#{driver_number}"
        lines.append(f"  #{driver_number} {name} — {lap_count} laps")
    return "\n".join(lines)


async def _run_sql_fast_path(query: str, session_id: uuid.UUID) -> str | None:
    """
    Dispatches to the right SQL lookup based on query keywords.
    Returns structured text if a match is found, None otherwise
    (fallback to vector search).
    """
    q = query.lower()

    if any(kw in q for kw in ["fastest lap", "quickest lap", "best lap", "fastest time"]):
        return await _fastest_lap_lookup(session_id)

    if any(kw in q for kw in ["most laps", "finished", "who won", "laps completed"]):
        return await _most_laps_lookup(session_id)

    # Unknown superlative — fall through to vector search
    return None


# ── Main RAG agent node ───────────────────────────────────────────────────────

async def rag_agent(state: AgentState) -> dict:
    """
    LangGraph node: answers questions using retrieved race knowledge.

    Two-path design:
    1. Superlative queries (fastest, most, who won) -> SQL aggregation for
       precise factual answers that vector search would get wrong.
    2. Everything else -> semantic search over RaceDocument embeddings
       (pgvector cosine distance) for contextual / historical questions.
    """
    query = state["query"]
    session_id = uuid.UUID(state["session_id"])
    session_key = state["session_key"]

    context: str | None = None

    if _is_superlative_query(query):
        context = await _run_sql_fast_path(query, session_id)

    if context is None:
        # Semantic vector search fallback
        async with AsyncSessionLocal() as db:
            docs = await search_similar_documents(
                db, query=query, session_key=session_key, limit=5
            )
        if not docs:
            return {
                "rag_output": (
                    "I don't have any indexed race documents for this session yet. "
                    "Try running the document build pipeline first."
                )
            }
        context = "\n\n".join(f"[{d.doc_type}] {d.content}" for d in docs)

    llm = get_llm(temperature=0.2)
    prompt = f"""You are a Formula 1 race historian answering questions using retrieved
race data.

Retrieved context:
{context}

User question: "{query}"

Answer using ONLY the information in the retrieved context above. Be specific with
driver names, teams, lap numbers and times. If the context doesn't fully answer the
question, say so explicitly rather than guessing. Keep the answer to 3-5 sentences."""

    response = llm.invoke(prompt)
    return {"rag_output": response.content}