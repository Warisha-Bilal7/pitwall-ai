from sqlalchemy import Column, String, Float, Integer, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector
import uuid
from datetime import datetime


class Base(DeclarativeBase):
    pass


class Season(Base):
    __tablename__ = "seasons"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    year = Column(Integer, nullable=False, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    meetings = relationship("Meeting", back_populates="season")


class Meeting(Base):
    """A race weekend (e.g. 2024 British Grand Prix)"""
    __tablename__ = "meetings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    season_id = Column(UUID(as_uuid=True), ForeignKey("seasons.id"))
    meeting_key = Column(Integer, unique=True, nullable=False)  # OpenF1 key
    meeting_name = Column(String(255), nullable=False)
    circuit_short_name = Column(String(100))
    country_name = Column(String(100))
    date_start = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    season = relationship("Season", back_populates="meetings")
    sessions = relationship("Session", back_populates="meeting")


class Session(Base):
    """A single session within a meeting (FP1, Qualifying, Race, etc.)"""
    __tablename__ = "sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meeting_id = Column(UUID(as_uuid=True), ForeignKey("meetings.id"))
    session_key = Column(Integer, unique=True, nullable=False)  # OpenF1 key
    session_name = Column(String(100), nullable=False)  # "Race", "Qualifying", etc.
    session_type = Column(String(50))                   # "Race", "Practice", "Qualifying"
    date_start = Column(DateTime)
    date_end = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    meeting = relationship("Meeting", back_populates="sessions")
    laps = relationship("Lap", back_populates="session")
    drivers = relationship("Driver", back_populates="session")
    pit_stops = relationship("PitStop", back_populates="session")


class Driver(Base):
    """Driver entry for a specific session"""
    __tablename__ = "drivers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id"))
    driver_number = Column(Integer, nullable=False)
    broadcast_name = Column(String(100))
    full_name = Column(String(150))
    name_acronym = Column(String(10))
    team_name = Column(String(100))
    team_colour = Column(String(10))
    country_code = Column(String(10))
    headshot_url = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("Session", back_populates="drivers")
    laps = relationship("Lap", back_populates="driver")


class Lap(Base):
    """Individual lap record"""
    __tablename__ = "laps"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id"))
    driver_id = Column(UUID(as_uuid=True), ForeignKey("drivers.id"))
    driver_number = Column(Integer, nullable=False)
    lap_number = Column(Integer, nullable=False)
    lap_duration = Column(Float)           # seconds
    i1_speed = Column(Float)               # km/h at intermediate 1
    i2_speed = Column(Float)               # km/h at intermediate 2
    st_speed = Column(Float)               # km/h at speed trap
    duration_sector_1 = Column(Float)
    duration_sector_2 = Column(Float)
    duration_sector_3 = Column(Float)
    is_pit_out_lap = Column(Boolean, default=False)
    segments_sector_1 = Column(Text)       # JSON string of mini-sectors
    segments_sector_2 = Column(Text)
    segments_sector_3 = Column(Text)
    date_start = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("Session", back_populates="laps")
    driver = relationship("Driver", back_populates="laps")


class PitStop(Base):
    """Pit stop event"""
    __tablename__ = "pit_stops"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id"))
    driver_number = Column(Integer, nullable=False)
    lap_number = Column(Integer)
    pit_duration = Column(Float)           # seconds in pit lane
    date = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("Session", back_populates="pit_stops")


class RaceDocument(Base):
    """Embedded race documents for RAG (Phase 3)"""
    __tablename__ = "race_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_key = Column(Integer)
    doc_type = Column(String(50))          # "race_summary", "strategy_note", etc.
    content = Column(Text, nullable=False)
    embedding = Column(Vector(384))        # sentence-transformers all-MiniLM-L6-v2
    metadata_ = Column("metadata", Text)   # JSON string
    created_at = Column(DateTime, default=datetime.utcnow)