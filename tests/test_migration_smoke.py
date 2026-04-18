"""Smoke tests for sqlite-backed API and MCP-compatible query layer."""
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
        os.environ["OAC_BACKEND"] = "sqlite"
        os.environ["OAC_DB_PATH"] = self.db_path

        store = SqliteStore(self.db_path)
        store.create_schema()
        store.insert_events(
            [
                {
                    "catalog": "sne",
                    "name": "SNTEST",
                    "normalized_name": "sntest",
                    "summary_json": '{"name":"SNTEST","catalog":"sne","alias":[{"value":"SNTEST"}],"ra":[{"value":"12:00:00"}],"dec":[{"value":"+02:00:00"}],"redshift":[{"value":"0.1"}]}',
                    "full_json": None,
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


if __name__ == "__main__":
    unittest.main()
