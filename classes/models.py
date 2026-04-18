"""SQLAlchemy models for persisted OAC API data."""
from sqlalchemy import Column, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class EventRecord(Base):
    """Persisted event data from astrocatalog repositories."""

    __tablename__ = "events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    catalog = Column(String(64), nullable=False, index=True)
    name = Column(String(255), nullable=False, index=True)
    normalized_name = Column(String(255), nullable=False, index=True)
    summary_json = Column(Text, nullable=False)
    full_json = Column(Text, nullable=True)
    ra_deg = Column(Float, nullable=True, index=True)
    dec_deg = Column(Float, nullable=True, index=True)

    __table_args__ = (UniqueConstraint("catalog", "name", name="uix_catalog_name"),)


class AliasRecord(Base):
    """Alias lookups for event resolution."""

    __tablename__ = "aliases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    catalog = Column(String(64), nullable=False, index=True)
    event_name = Column(String(255), nullable=False, index=True)
    alias_raw = Column(String(255), nullable=False)
    alias_norm = Column(String(255), nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint(
            "catalog", "event_name", "alias_norm", name="uix_alias_catalog_event_norm"
        ),
    )


class IngestMeta(Base):
    """Tracks the provenance of ingested static repositories."""

    __tablename__ = "ingest_meta"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(64), nullable=False, unique=True)
    value = Column(Text, nullable=False)

