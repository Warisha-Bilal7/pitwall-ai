from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.f1_models import Session, Meeting, Driver, Lap, PitStop
import uuid


async def build_session_summary(db: AsyncSession, session_id: uuid.UUID) -> str:
    """
    One overall text summary for a session: meeting info, who raced, pit stop counts.
    This becomes a single RaceDocument of doc_type='session_summary'.
    """
    result = await db.execute(
        select(Session, Meeting)
        .join(Meeting, Session.meeting_id == Meeting.id)
        .where(Session.id == session_id)
    )
    row = result.one_or_none()
    if not row:
        return ""
    session, meeting = row

    drivers_result = await db.execute(
        select(Driver).where(Driver.session_id == session_id).order_by(Driver.driver_number)
    )
    drivers = drivers_result.scalars().all()

    pits_result = await db.execute(
        select(PitStop).where(PitStop.session_id == session_id)
    )
    pit_stops = pits_result.scalars().all()

    driver_lines = [
        f"#{d.driver_number} {d.full_name} ({d.team_name})" for d in drivers
    ]

    lines = [
        f"Session: {session.session_name} ({session.session_type}) at the "
        f"{meeting.meeting_name}, {meeting.country_name}.",
        f"Session date: {session.date_start}.",
        f"Drivers in this session ({len(drivers)} total): {', '.join(driver_lines)}.",
        f"Total pit stops recorded: {len(pit_stops)}.",
    ]
    return " ".join(lines)


async def build_driver_race_document(
    db: AsyncSession, session_id: uuid.UUID, driver: Driver
) -> str:
    """
    One text document per driver per session: lap pace summary + pit stop details.
    This becomes a RaceDocument of doc_type='driver_race_summary'.
    """
    laps_result = await db.execute(
        select(Lap)
        .where(Lap.session_id == session_id, Lap.driver_number == driver.driver_number)
        .order_by(Lap.lap_number)
    )
    laps = laps_result.scalars().all()

    pits_result = await db.execute(
        select(PitStop)
        .where(
            PitStop.session_id == session_id,
            PitStop.driver_number == driver.driver_number,
        )
        .order_by(PitStop.lap_number)
    )
    pit_stops = pits_result.scalars().all()

    valid_laps = [l for l in laps if l.lap_duration]
    if valid_laps:
        durations = [l.lap_duration for l in valid_laps]
        fastest = min(durations)
        slowest = max(durations)
        average = sum(durations) / len(durations)
        fastest_lap_number = next(
            l.lap_number for l in valid_laps if l.lap_duration == fastest
        )
        pace_summary = (
            f"Completed {len(laps)} laps. Fastest lap: {fastest:.3f}s on lap "
            f"{fastest_lap_number}. Slowest lap: {slowest:.3f}s. "
            f"Average lap time: {average:.3f}s."
        )
    else:
        pace_summary = f"Completed {len(laps)} laps. No valid lap time data recorded."

    if pit_stops:
        pit_lines = [
            f"lap {p.lap_number} ({p.pit_duration:.1f}s)" if p.pit_duration else f"lap {p.lap_number}"
            for p in pit_stops
        ]
        pit_summary = f"Made {len(pit_stops)} pit stop(s): {', '.join(pit_lines)}."
    else:
        pit_summary = "No pit stops recorded."

    lines = [
        f"Driver #{driver.driver_number} {driver.full_name} ({driver.team_name}) "
        f"in this session.",
        pace_summary,
        pit_summary,
    ]
    return " ".join(lines)


async def build_all_documents_for_session(
    db: AsyncSession, session_id: uuid.UUID
) -> list[dict]:
    """
    Builds the full set of text documents for a session:
    - 1 session_summary document
    - 1 driver_race_summary document per driver

    Returns a list of dicts: [{"doc_type": ..., "content": ...}, ...]
    Ready to be embedded and inserted as RaceDocument rows.
    """
    documents = []

    session_summary = await build_session_summary(db, session_id)
    if session_summary:
        documents.append({"doc_type": "session_summary", "content": session_summary})

    drivers_result = await db.execute(
        select(Driver).where(Driver.session_id == session_id).order_by(Driver.driver_number)
    )
    drivers = drivers_result.scalars().all()

    for driver in drivers:
        doc_text = await build_driver_race_document(db, session_id, driver)
        if doc_text:
            documents.append({"doc_type": "driver_race_summary", "content": doc_text})

    return documents