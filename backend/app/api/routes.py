from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.models.f1_models import Session, Driver, Lap, PitStop, Meeting
from typing import Optional
import uuid

router = APIRouter()


# ── Sessions ──────────────────────────────────────────────────────────────────

@router.get("/sessions")
async def list_sessions(
    year: Optional[int] = Query(None),
    session_type: Optional[str] = Query(None),
    limit: int = Query(20, le=100),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Session, Meeting.meeting_name, Meeting.country_name)
        .join(Meeting, Session.meeting_id == Meeting.id)
        .order_by(Session.date_start.desc())
        .limit(limit)
    )
    if session_type:
        stmt = stmt.where(Session.session_type == session_type)
    if year:
        stmt = stmt.where(func.extract("year", Session.date_start) == year)

    result = await db.execute(stmt)
    rows = result.all()
    return [
        {
            "id": str(s.id),
            "session_key": s.session_key,
            "session_name": s.session_name,
            "session_type": s.session_type,
            "date_start": s.date_start,
            "meeting_name": meeting_name,
            "country_name": country_name,
        }
        for s, meeting_name, country_name in rows
    ]


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Session, Meeting.meeting_name, Meeting.country_name)
        .join(Meeting, Session.meeting_id == Meeting.id)
        .where(Session.id == uuid.UUID(session_id))
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    s, meeting_name, country_name = row
    return {
        "id": str(s.id),
        "session_key": s.session_key,
        "session_name": s.session_name,
        "session_type": s.session_type,
        "date_start": s.date_start,
        "date_end": s.date_end,
        "meeting_name": meeting_name,
        "country_name": country_name,
    }


# ── Drivers ───────────────────────────────────────────────────────────────────

@router.get("/sessions/{session_id}/drivers")
async def get_drivers(session_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Driver)
        .where(Driver.session_id == uuid.UUID(session_id))
        .order_by(Driver.driver_number)
    )
    drivers = result.scalars().all()
    return [
        {
            "id": str(d.id),
            "driver_number": d.driver_number,
            "full_name": d.full_name,
            "name_acronym": d.name_acronym,
            "team_name": d.team_name,
            "team_colour": d.team_colour,
            "country_code": d.country_code,
        }
        for d in drivers
    ]


# ── Laps ──────────────────────────────────────────────────────────────────────

@router.get("/sessions/{session_id}/laps")
async def get_laps(
    session_id: str,
    driver_number: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Lap)
        .where(Lap.session_id == uuid.UUID(session_id))
        .order_by(Lap.driver_number, Lap.lap_number)
    )
    if driver_number:
        stmt = stmt.where(Lap.driver_number == driver_number)

    result = await db.execute(stmt)
    laps = result.scalars().all()
    return [
        {
            "driver_number": l.driver_number,
            "lap_number": l.lap_number,
            "lap_duration": l.lap_duration,
            "sector_1": l.duration_sector_1,
            "sector_2": l.duration_sector_2,
            "sector_3": l.duration_sector_3,
            "i1_speed": l.i1_speed,
            "st_speed": l.st_speed,
            "is_pit_out_lap": l.is_pit_out_lap,
        }
        for l in laps
    ]


# ── Pit stops ─────────────────────────────────────────────────────────────────

@router.get("/sessions/{session_id}/pit-stops")
async def get_pit_stops(session_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(PitStop)
        .where(PitStop.session_id == uuid.UUID(session_id))
        .order_by(PitStop.driver_number, PitStop.lap_number)
    )
    pits = result.scalars().all()
    return [
        {
            "driver_number": p.driver_number,
            "lap_number": p.lap_number,
            "pit_duration": p.pit_duration,
            "date": p.date,
        }
        for p in pits
    ]


# ── Ingest trigger ────────────────────────────────────────────────────────────

@router.post("/ingest/{session_key}")
async def trigger_ingest(session_key: int, db: AsyncSession = Depends(get_db)):
    """Trigger ingestion for a session key. Runs synchronously for now."""
    from ingestion.pipeline import ingest_session_to_db
    try:
        await ingest_session_to_db(session_key)
        return {"status": "ok", "session_key": session_key}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))