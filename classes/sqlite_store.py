"""SQLite-backed persistence and lookup helpers for OAC API."""
import json
import os
from collections import OrderedDict, defaultdict

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from classes.models import AliasRecord, Base, EventRecord, IngestMeta


class SqliteStore(object):
    """Thin SQLAlchemy wrapper for catalog event data."""

    def __init__(self, db_path):
        """Initialize an engine/session factory for a sqlite database."""
        self.db_path = db_path
        self.db_url = "sqlite:///" + db_path
        self.engine = create_engine(self.db_url, future=True)

    def exists(self):
        """Return whether sqlite file is present on disk."""
        return os.path.exists(self.db_path)

    def create_schema(self):
        """Create SQLAlchemy schema in the backing database."""
        Base.metadata.create_all(self.engine)

    def clear_all(self):
        """Delete all rows from tables."""
        with Session(self.engine) as session:
            session.query(AliasRecord).delete()
            session.query(EventRecord).delete()
            session.query(IngestMeta).delete()
            session.commit()

    def upsert_meta(self, key, value):
        """Insert/update ingest metadata key/value pairs."""
        with Session(self.engine) as session:
            record = session.execute(
                select(IngestMeta).where(IngestMeta.key == key)
            ).scalar_one_or_none()
            if record is None:
                record = IngestMeta(key=key, value=value)
                session.add(record)
            else:
                record.value = value
            session.commit()

    def insert_events(self, rows):
        """Bulk insert event rows."""
        with Session(self.engine) as session:
            session.add_all([EventRecord(**row) for row in rows])
            session.commit()

    def insert_aliases(self, rows):
        """Bulk insert alias rows."""
        with Session(self.engine) as session:
            session.add_all([AliasRecord(**row) for row in rows])
            session.commit()

    def load_catalogs(self):
        """Load summary catalog records into legacy in-memory layout."""
        catalogs = OrderedDict()
        cat_keys = OrderedDict()
        with Session(self.engine) as session:
            records = session.execute(
                select(EventRecord).order_by(EventRecord.catalog, EventRecord.name)
            ).scalars()
            for record in records:
                if record.catalog not in catalogs:
                    catalogs[record.catalog] = OrderedDict()
                    cat_keys[record.catalog] = set()
                summary = json.loads(record.summary_json, object_pairs_hook=OrderedDict)
                summary["catalog"] = record.catalog
                catalogs[record.catalog][record.name] = summary
                cat_keys[record.catalog].update(summary.keys())
        return catalogs, cat_keys

    def load_all_catalog_names(self):
        """Return catalog names known by the sqlite snapshot."""
        with Session(self.engine) as session:
            rows = session.execute(
                select(EventRecord.catalog).distinct().order_by(EventRecord.catalog)
            ).all()
            return [catalog for (catalog,) in rows]

    def load_alias_index(self):
        """Return alias lookup structures in API-native shape."""
        aliases = OrderedDict()
        all_aliases = set()
        with Session(self.engine) as session:
            records = session.execute(
                select(AliasRecord).order_by(
                    AliasRecord.alias_norm, AliasRecord.catalog, AliasRecord.event_name
                )
            ).scalars()
            for record in records:
                aliases.setdefault(record.alias_norm, []).append(
                    [record.catalog, record.event_name, record.alias_raw]
                )
                all_aliases.add(record.alias_raw.lower())
        return aliases, all_aliases

    def get_full_event(self, catalog, event_name):
        """Return full event JSON from DB if available."""
        with Session(self.engine) as session:
            record = session.execute(
                select(EventRecord).where(
                    EventRecord.catalog == catalog, EventRecord.name == event_name
                )
            ).scalar_one_or_none()
            if record is None:
                return None
            payload = record.full_json if record.full_json else record.summary_json
            full_event = json.loads(payload, object_pairs_hook=OrderedDict)
            full_event["catalog"] = catalog
            return full_event

    def get_full_event_any_alias(self, catalog, candidate_event_names):
        """Resolve first full event payload for candidate names."""
        for event_name in candidate_event_names:
            event = self.get_full_event(catalog, event_name)
            if event is not None:
                return event_name, event
        return None, None

    def coordinates(self):
        """Yield event names and coordinate tuples if present."""
        rows = []
        with Session(self.engine) as session:
            records = session.execute(
                select(EventRecord.name, EventRecord.ra_deg, EventRecord.dec_deg)
            ).all()
            for name, ra_deg, dec_deg in records:
                if ra_deg is None or dec_deg is None:
                    continue
                rows.append((name, ra_deg, dec_deg))
        return rows

    def counts_by_catalog(self):
        """Return row counts by catalog for diagnostics."""
        counters = defaultdict(int)
        with Session(self.engine) as session:
            records = session.execute(select(EventRecord.catalog)).all()
            for (catalog,) in records:
                counters[catalog] += 1
        return dict(sorted(counters.items()))
