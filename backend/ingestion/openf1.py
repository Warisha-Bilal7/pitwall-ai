import httpx
import asyncio
from typing import Optional
from datetime import datetime

BASE_URL = "https://api.openf1.org/v1"


class OpenF1Client:
    """
    Async client for the OpenF1 API.
    All methods return raw dicts ready to be inserted into the DB.
    Docs: https://openf1.org/
    """

    def __init__(self):
        self.client = httpx.AsyncClient(
            base_url=BASE_URL,
            timeout=30.0,
            headers={"Accept": "application/json"},
        )

    async def close(self):
        await self.client.aclose()

    async def _get(self, endpoint: str, params: dict = None) -> list[dict]:
        """Raw GET with basic error handling."""
        response = await self.client.get(endpoint, params=params or {})
        response.raise_for_status()
        return response.json()

    # ── Meetings ─────────────────────────────────────────────────────────────

    async def get_meetings(self, year: Optional[int] = None) -> list[dict]:
        """Fetch all race weekends, optionally filtered by year."""
        params = {}
        if year:
            params["year"] = year
        return await self._get("/meetings", params)

    async def get_latest_meeting(self) -> dict:
        """Fetch the most recent race weekend."""
        results = await self._get("/meetings", {"meeting_key": "latest"})
        return results[0] if results else {}

    # ── Sessions ─────────────────────────────────────────────────────────────

    async def get_sessions(
        self,
        meeting_key: Optional[int] = None,
        session_type: Optional[str] = None,
        year: Optional[int] = None,
    ) -> list[dict]:
        """Fetch sessions. Filter by meeting, type ('Race','Practice','Qualifying'), or year."""
        params = {}
        if meeting_key:
            params["meeting_key"] = meeting_key
        if session_type:
            params["session_type"] = session_type
        if year:
            params["year"] = year
        return await self._get("/sessions", params)

    async def get_latest_session(self) -> dict:
        """Fetch the most recent session."""
        results = await self._get("/sessions", {"session_key": "latest"})
        return results[0] if results else {}

    # ── Drivers ──────────────────────────────────────────────────────────────

    async def get_drivers(
        self,
        session_key: int,
        driver_number: Optional[int] = None,
    ) -> list[dict]:
        params = {"session_key": session_key}
        if driver_number:
            params["driver_number"] = driver_number
        return await self._get("/drivers", params)

    # ── Laps ─────────────────────────────────────────────────────────────────

    async def get_laps(
        self,
        session_key: int,
        driver_number: Optional[int] = None,
        lap_number: Optional[int] = None,
    ) -> list[dict]:
        """Fetch lap data. Can filter to a single driver or specific lap."""
        params = {"session_key": session_key}
        if driver_number:
            params["driver_number"] = driver_number
        if lap_number:
            params["lap_number"] = lap_number
        return await self._get("/laps", params)

    # ── Pit stops ────────────────────────────────────────────────────────────

    async def get_pit_stops(
        self,
        session_key: int,
        driver_number: Optional[int] = None,
    ) -> list[dict]:
        params = {"session_key": session_key}
        if driver_number:
            params["driver_number"] = driver_number
        return await self._get("/pit", params)

    # ── Car telemetry ─────────────────────────────────────────────────────────

    async def get_car_data(
        self,
        session_key: int,
        driver_number: int,
    ) -> list[dict]:
        """
        High-frequency car data (throttle, brake, RPM, gear, speed, DRS).
        Returns ~3.7Hz samples. Large payload — use per-driver only.
        """
        params = {
            "session_key": session_key,
            "driver_number": driver_number,
        }
        return await self._get("/car_data", params)

    # ── Position ─────────────────────────────────────────────────────────────

    async def get_position(
        self,
        session_key: int,
        driver_number: Optional[int] = None,
    ) -> list[dict]:
        """Track position data (x, y, z coordinates)."""
        params = {"session_key": session_key}
        if driver_number:
            params["driver_number"] = driver_number
        return await self._get("/location", params)

    # ── Intervals (live gaps) ─────────────────────────────────────────────────

    async def get_intervals(self, session_key: int) -> list[dict]:
        """Gap to leader and gap to car ahead for all drivers."""
        return await self._get("/intervals", {"session_key": session_key})

    # ── Race control ──────────────────────────────────────────────────────────

    async def get_race_control(self, session_key: int) -> list[dict]:
        """Race control messages: flags, VSC, SC, penalties."""
        return await self._get("/race_control", {"session_key": session_key})


# ── Standalone ingestion script ───────────────────────────────────────────────

async def ingest_session(session_key: int):
    """
    Fetch and print all data for a given session_key.
    Replace print() with DB inserts in Phase 2.
    """
    client = OpenF1Client()

    try:
        print(f"\n🏎  Fetching data for session {session_key}...\n")

        # Drivers
        drivers = await client.get_drivers(session_key)
        print(f"  👤 Drivers found: {len(drivers)}")
        for d in drivers[:3]:
            print(f"     #{d.get('driver_number')} {d.get('full_name')} — {d.get('team_name')}")
        if len(drivers) > 3:
            print(f"     ... and {len(drivers) - 3} more")

        # Laps
        laps = await client.get_laps(session_key)
        print(f"\n  🔄 Laps found: {len(laps)}")
        if laps:
            sample = laps[0]
            print(f"     Sample — Driver #{sample.get('driver_number')} "
                  f"Lap {sample.get('lap_number')}: "
                  f"{sample.get('lap_duration')}s")

        # Pit stops
        pits = await client.get_pit_stops(session_key)
        print(f"\n  🔧 Pit stops found: {len(pits)}")
        if pits:
            sample = pits[0]
            print(f"     Sample — Driver #{sample.get('driver_number')} "
                  f"Lap {sample.get('lap_number')}: "
                  f"{sample.get('pit_duration')}s")

        # Race control messages
        rc = await client.get_race_control(session_key)
        print(f"\n  🚩 Race control messages: {len(rc)}")
        if rc:
            print(f"     Latest: {rc[-1].get('message', '')}")

        print(f"\n✅ Ingestion complete for session {session_key}")

    finally:
        await client.close()


async def fetch_latest():
    """Quick check: print the latest meeting and session."""
    client = OpenF1Client()
    try:
        meeting = await client.get_latest_meeting()
        session = await client.get_latest_session()
        print("\n📍 Latest meeting:")
        print(f"   {meeting.get('meeting_name')} — {meeting.get('country_name')}")
        print(f"   Key: {meeting.get('meeting_key')}")
        print(f"\n📍 Latest session:")
        print(f"   {session.get('session_name')} — {session.get('date_start')}")
        print(f"   Key: {session.get('session_key')}")
    finally:
        await client.close()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        # python openf1.py 9158   ← ingest specific session
        asyncio.run(ingest_session(int(sys.argv[1])))
    else:
        # python openf1.py        ← show latest meeting/session
        asyncio.run(fetch_latest())