"""Smoke tests for sqlite-backed API and MCP-compatible query layer."""
import json
import os
import tempfile
import unittest
from collections import OrderedDict

from classes.apidata import ApiData
from classes.sqlite_store import SqliteStore


def _sample_summary(name, catalog):
    return OrderedDict(
        [
            ("name", name),
            ("catalog", catalog),
            ("alias", [{"value": name}]),
            ("ra", [{"value": "12:00:00"}]),
            ("dec", [{"value": "+02:00:00"}]),
            ("redshift", [{"value": "0.1"}]),
        ]
    )


class MigrationSmokeTests(unittest.TestCase):
    """Validate compatibility plumbing around sqlite backend."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmpdir.name, "oacapi.db")
        self.ac_path = os.path.join(self.tmpdir.name, "astrocats", "astrocats")
        os.environ["OAC_BACKEND"] = "sqlite"
        os.environ["OAC_DB_PATH"] = self.db_path

        event_dir = os.path.join(self.ac_path, "supernovae", "output", "json")
        os.makedirs(event_dir, exist_ok=True)
        event_payload = {
            "SNTEST": {
                "name": "SNTEST",
                "alias": [{"value": "SNTEST"}],
                "redshift": [{"value": "0.1"}],
                "sources": [{"name": "UnitTestSource"}],
            }
        }
        with open(os.path.join(event_dir, "SNTEST.json"), "w") as handle:
            json.dump(event_payload, handle)

        store = SqliteStore(self.db_path)
        store.create_schema()
        store.insert_events(
            [
                {
                    "catalog": "sne",
                    "name": "SNTEST",
                    "normalized_name": "sntest",
                    "summary_json": '{"name":"SNTEST","catalog":"sne","alias":[{"value":"SNTEST"}],"ra":[{"value":"12:00:00"}],"dec":[{"value":"+02:00:00"}],"redshift":[{"value":"0.1"}]}',
                    "event_path": os.path.join(event_dir, "SNTEST.json"),
                    "ra_deg": 180.0,
                    "dec_deg": 2.0,
                }
            ]
        )
        store.insert_aliases(
            [
                {
                    "catalog": "sne",
                    "event_name": "SNTEST",
                    "alias_raw": "sntest",
                    "alias_norm": "sntest",
                }
            ]
        )

    def tearDown(self):
        self.tmpdir.cleanup()
        os.environ.pop("OAC_BACKEND", None)
        os.environ.pop("OAC_DB_PATH", None)

    def test_apidata_uses_sqlite_when_present(self):
        """ApiData should detect sqlite backend when DB exists."""
        apidata = ApiData()
        self.assertTrue(apidata.use_sqlite)
        catalogs, keys = apidata._store.load_catalogs()
        self.assertIn("sne", catalogs)
        self.assertIn("SNTEST", catalogs["sne"])
        self.assertIn("redshift", keys["sne"])

    def test_query_service_executes(self):
        """QueryService should invoke API semantics under test context."""
        # Import lazily after environment has been prepared.
        from classes.query_service import QueryService

        service = QueryService()
        result = service.execute("sne", event_name="SNTEST", quantity_name="redshift")
        self.assertEqual(result["status"], 200)
        self.assertEqual(result["kind"], "json")
        self.assertIn("SNTEST", result["body"])

    def test_full_query_uses_event_json_path(self):
        """Full queries should load event payload from JSON file path."""
        from api import Catalog, apidata

        apidata._AC_PATH = self.ac_path
        resource = Catalog()
        from api import app

        with app.test_request_context(
            method="GET",
            path="/",
            query_string={"full": "1"},
        ):
            result = resource.get("sne", event_name="SNTEST")
        payload = result.get("SNTEST", {})
        self.assertIn("sources", payload)
        self.assertEqual(payload["sources"][0]["name"], "UnitTestSource")


if __name__ == "__main__":
    unittest.main()
