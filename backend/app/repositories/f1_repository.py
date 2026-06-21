from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.models.f1_models import Season, Meeting, Session, Driver, Lap, PitStop
from datetime import datetime
from typing import Optional
import uuid


# ── Season ────────────────────────────────────────────────────────────────────

async def get_or_create_season(db: AsyncSession, year: int) -> Season:
    result = await db.execute(select(Season).where(Season.year == year))
    season = result.scalar_one_or_none()
    if not season:
        season = Season(id=uuid.uuid4(), year=year)
        db.add(season)
        await db.flush()
    return season


# ── Meeting ───────────────────────────────────────────────────────────────────

async def upsert_meeting(db: AsyncSession, data: dict, season_id: uuid.UUID) -> Meeting:
    result = await db.execute(
        select(Meeting).where(Meeting.meeting_key == data["meeting_key"])
    )
    meeting = result.scalar_one_or_none()
    if not meeting:
        meeting = Meeting(
            id=uuid.uuid4(),
            season_id=season_id,
            meeting_key=data["meeting_key"],
            meeting_name=data.get("meeting_name", ""),
            circuit_short_name=data.get("circuit_short_name"),
            country_name=data.get("country_name"),
            date_start=_parse_dt(data.get("date_start")),
        )
        db.add(meeting)
        await db.flush()
    return meeting


# ── Session ───────────────────────────────────────────────────────────────────

async def upsert_session(db: AsyncSession, data: dict, meeting_id: uuid.UUID) -> Session:
    result = await db.execute(
        select(Session).where(Session.session_key == data["session_key"])
    )
    session = result.scalar_one_or_none()
    if not session:
        session = Session(
            id=uuid.uuid4(),
            meeting_id=meeting_id,
            session_key=data["session_key"],
            session_name=data.get("session_name", ""),
            session_type=data.get("session_type"),
            date_start=_parse_dt(data.get("date_start")),
            date_end=_parse_dt(data.get("date_end")),
        )
        db.add(session)
        await db.flush()
    return session


# ── Drivers ───────────────────────────────────────────────────────────────────

async def upsert_drivers(
    db: AsyncSession, drivers_data: list[dict], session_id: uuid.UUID
) -> dict[int, Driver]:
    """Upsert all drivers for a session. Returns a dict of driver_number → Driver."""
    driver_map = {}
    for data in drivers_data:
        driver_number = data.get("driver_number")
        if not driver_number:
            continue
        result = await db.execute(
            select(Driver).where(
                Driver.session_id == session_id,
                Driver.driver_number == driver_number,
            )
        )
        driver = result.scalar_one_or_none()
        if not driver:
            driver = Driver(
                id=uuid.uuid4(),
                session_id=session_id,
                driver_number=driver_number,
                broadcast_name=data.get("broadcast_name"),
                full_name=data.get("full_name"),
                name_acronym=data.get("name_acronym"),
                team_name=data.get("team_name"),
                team_colour=data.get("team_colour"),
                country_code=data.get("country_code"),
                headshot_url=data.get("headshot_url"),
            )
            db.add(driver)
        driver_map[driver_number] = driver
    await db.flush()
    return driver_map


# ── Laps ──────────────────────────────────────────────────────────────────────

async def insert_laps(
    db: AsyncSession,
    laps_data: list[dict],
    session_id: uuid.UUID,
    driver_map: dict[int, Driver],
) -> int:
    """Insert laps — skips any lap that already exists for this session+driver+lap_number."""
    result = await db.execute(
        select(Lap.driver_number, Lap.lap_number).where(Lap.session_id == session_id)
    )
    existing_laps = {(row[0], row[1]) for row in result.all()}

    inserted = 0
    for data in laps_data:
        driver_number = data.get("driver_number")
        lap_number = data.get("lap_number")
        if not driver_number or not lap_number:
            continue

        # skip if already exists
        if (driver_number, lap_number) in existing_laps:
            continue

        driver = driver_map.get(driver_number)
        lap = Lap(
            id=uuid.uuid4(),
            session_id=session_id,
            driver_id=driver.id if driver else None,
            driver_number=driver_number,
            lap_number=lap_number,
            lap_duration=data.get("lap_duration"),
            i1_speed=data.get("i1_speed"),
            i2_speed=data.get("i2_speed"),
            st_speed=data.get("st_speed"),
            duration_sector_1=data.get("duration_sector_1"),
            duration_sector_2=data.get("duration_sector_2"),
            duration_sector_3=data.get("duration_sector_3"),
            is_pit_out_lap=data.get("is_pit_out_lap", False),
            segments_sector_1=str(data.get("segments_sector_1", "")),
            segments_sector_2=str(data.get("segments_sector_2", "")),
            segments_sector_3=str(data.get("segments_sector_3", "")),
            date_start=_parse_dt(data.get("date_start")),
        )
        db.add(lap)
        existing_laps.add((driver_number, lap_number))
        inserted += 1
    await db.flush()
    return inserted


# ── Pit stops ─────────────────────────────────────────────────────────────────

async def insert_pit_stops(
    db: AsyncSession, pits_data: list[dict], session_id: uuid.UUID
) -> int:
    result = await db.execute(
        select(PitStop.driver_number, PitStop.lap_number).where(PitStop.session_id == session_id)
    )
    existing_pits = {(row[0], row[1]) for row in result.all()}

    inserted = 0
    for data in pits_data:
        driver_number = data.get("driver_number")
        lap_number = data.get("lap_number")
        if not driver_number:
            continue

        if (driver_number, lap_number) in existing_pits:
            continue

        pit = PitStop(
            id=uuid.uuid4(),
            session_id=session_id,
            driver_number=driver_number,
            lap_number=lap_number,
            pit_duration=data.get("pit_duration"),
            date=_parse_dt(data.get("date")),
        )
        db.add(pit)
        existing_pits.add((driver_number, lap_number))
        inserted += 1
    await db.flush()
    return inserted


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_dt(value) -> Optional[datetime]:
    """Parse ISO datetime strings from OpenF1 into Python datetime objects."""
    if not value:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    try:
        # OpenF1 returns strings like "2024-07-07T13:00:00+00:00"
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt.replace(tzinfo=None)
    except (ValueError, TypeError):
        return None