import asyncio
import sys
from app.database import AsyncSessionLocal
from app.repositories.f1_repository import (
    get_or_create_season,
    upsert_meeting,
    upsert_session,
    upsert_drivers,
    insert_laps,
    insert_pit_stops,
)
from ingestion.openf1 import OpenF1Client


async def ingest_session_to_db(session_key: int):
    """
    Full pipeline: fetch from OpenF1 → write to Neon DB.
    Safe to re-run — all writes are upsert/skip-if-exists.
    """
    client = OpenF1Client()

    async with AsyncSessionLocal() as db:
        async with db.begin():
            try:
                print(f"\n🏎  Ingesting session {session_key} into Neon...\n")

                # 1. Fetch session metadata from OpenF1
                sessions_data = await client.get_sessions(session_key=session_key)
                if not sessions_data:
                    print(f"❌ No session found for key {session_key}")
                    return
                session_data = sessions_data[0]

                # 2. Fetch meeting metadata
                meetings_data = await client.get_meetings()
                meeting_data = next(
                    (m for m in meetings_data if m["meeting_key"] == session_data["meeting_key"]),
                    None,
                )
                if not meeting_data:
                    print(f"❌ No meeting found for session {session_key}")
                    return

                # 3. Season
                year = meeting_data.get("year") or int(
                    str(meeting_data.get("date_start", "2024"))[:4]
                )
                season = await get_or_create_season(db, year)
                print(f"  ✅ Season {year} (id: {season.id})")

                # 4. Meeting
                meeting = await upsert_meeting(db, meeting_data, season.id)
                print(f"  ✅ Meeting: {meeting.meeting_name} — {meeting.country_name}")

                # 5. Session
                session = await upsert_session(db, session_data, meeting.id)
                print(f"  ✅ Session: {session.session_name} ({session.session_type})")

                # 6. Drivers
                drivers_data = await client.get_drivers(session_key)
                driver_map = await upsert_drivers(db, drivers_data, session.id)
                print(f"  ✅ Drivers: {len(driver_map)} upserted")

                # 7. Laps
                laps_data = await client.get_laps(session_key)
                laps_inserted = await insert_laps(db, laps_data, session.id, driver_map)
                print(f"  ✅ Laps: {laps_inserted} inserted ({len(laps_data)} fetched)")

                # 8. Pit stops
                pits_data = await client.get_pit_stops(session_key)
                pits_inserted = await insert_pit_stops(db, pits_data, session.id)
                print(f"  ✅ Pit stops: {pits_inserted} inserted")

                print(f"\n🏁 Ingestion complete for session {session_key}")

            except Exception as e:
                print(f"\n❌ Ingestion failed: {e}")
                raise
            finally:
                await client.close()


if __name__ == "__main__":
    key = int(sys.argv[1]) if len(sys.argv) > 1 else 9158
    asyncio.run(ingest_session_to_db(key))