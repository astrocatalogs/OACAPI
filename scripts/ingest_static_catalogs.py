"""Ingest static astrocatalog repositories into a SQLite snapshot."""
import argparse
import json
import logging
import os
import re
from collections import OrderedDict
from datetime import datetime

from astropy.coordinates import SkyCoord as coord
from astropy import units as un

from classes.apidata import ApiData
from classes.sqlite_store import SqliteStore

LOGGER = logging.getLogger("ingest")


def normalize_alias(value):
    """Normalize aliases to the form used by API lookup tables."""
    return str(value).lower().replace(" ", "")


def alias_variants(value):
    """Generate API-compatible alias variants."""
    out = set()
    lowered = str(value).lower()
    out.add(lowered)
    if lowered.startswith(("sn", "at")):
        out.add(re.sub(r"^(sn|at)", "", lowered))
    return sorted(out)


def read_json(path):
    """Read JSON preserving ordering to reduce output drift."""
    with open(path, "r") as handle:
        return json.load(handle, object_pairs_hook=OrderedDict)


def parse_degrees(event):
    """Try to compute decimal degrees from RA/Dec fields."""
    ra = event.get("ra")
    dec = event.get("dec")
    if not ra or not dec:
        return None, None
    ra_val = ra[0].get("value") if isinstance(ra, list) and ra else None
    dec_val = dec[0].get("value") if isinstance(dec, list) and dec else None
    if not ra_val or not dec_val:
        return None, None

    try:
        c = coord(str(ra_val), str(dec_val), unit=(un.hourangle, un.deg))
    except Exception:
        try:
            c = coord(float(ra_val), float(dec_val), unit=(un.deg, un.deg))
        except Exception:
            return None, None
    return float(c.ra.deg), float(c.dec.deg)


def load_full_event(apidata, catalog, event_name):
    """Load full event JSON if present, otherwise return None."""
    catalog_meta = apidata._CATS[catalog]
    base_dir = os.path.join(apidata._AC_PATH, catalog_meta[0], "output", "json")
    primary_path = os.path.join(base_dir, event_name.replace("/", "_") + ".json")
    if not os.path.exists(primary_path):
        return None
    payload = read_json(primary_path)
    _, event = payload.popitem()
    event["catalog"] = catalog
    return event


def ingest_catalogs(apidata):
    """Yield event and alias rows from all configured catalogs."""
    event_rows = []
    alias_rows = []
    for catalog, cat_meta in apidata._CATS.items():
        catalog_path = os.path.join(apidata._AC_PATH, cat_meta[0], "output", cat_meta[1])
        if not os.path.exists(catalog_path):
            LOGGER.warning("Catalog file missing: %s", catalog_path)
            continue
        entries = read_json(catalog_path)
        for entry in entries:
            name = entry["name"]
            summary = OrderedDict(entry)
            summary["catalog"] = catalog
            ra_deg, dec_deg = parse_degrees(summary)
            full_event = load_full_event(apidata, catalog, name)
            event_rows.append(
                {
                    "catalog": catalog,
                    "name": name,
                    "normalized_name": normalize_alias(name),
                    "summary_json": json.dumps(summary, separators=(",", ":"), ensure_ascii=False),
                    "full_json": (
                        json.dumps(full_event, separators=(",", ":"), ensure_ascii=False)
                        if full_event is not None
                        else None
                    ),
                    "ra_deg": ra_deg,
                    "dec_deg": dec_deg,
                }
            )
            variants = set(alias_variants(name))
            for alias in summary.get("alias", []):
                alias_value = alias.get("value")
                if alias_value:
                    variants.update(alias_variants(alias_value))
            for variant in variants:
                alias_rows.append(
                    {
                        "catalog": catalog,
                        "event_name": name,
                        "alias_raw": variant,
                        "alias_norm": normalize_alias(variant),
                    }
                )
    return event_rows, alias_rows


def parse_args():
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db-path",
        default=os.environ.get("OAC_DB_PATH", "/data/oacapi.db"),
        help="Path for generated sqlite database.",
    )
    parser.add_argument(
        "--ac-path",
        default=os.environ.get("AC_PATH", ApiData._AC_PATH),
        help="Path to astrocats repositories root.",
    )
    return parser.parse_args()


def main():
    """Entrypoint for ingest command."""
    logging.basicConfig(level=logging.INFO)
    args = parse_args()
    apidata = ApiData()
    apidata._AC_PATH = args.ac_path

    db_dir = os.path.dirname(args.db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    store = SqliteStore(args.db_path)
    store.create_schema()
    store.clear_all()

    event_rows, alias_rows = ingest_catalogs(apidata)
    LOGGER.info("Ingesting %d events and %d aliases", len(event_rows), len(alias_rows))
    if event_rows:
        store.insert_events(event_rows)
    if alias_rows:
        store.insert_aliases(alias_rows)
    store.upsert_meta("ingest_time_utc", datetime.utcnow().isoformat() + "Z")
    store.upsert_meta("event_count", str(len(event_rows)))
    LOGGER.info("SQLite snapshot ready at %s", args.db_path)


if __name__ == "__main__":
    main()
