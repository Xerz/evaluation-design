from __future__ import annotations

import hashlib
import importlib.util
import json
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SERVER_PATH = PROJECT_ROOT / "db-viewer" / "server.py"
DB_PATH = PROJECT_ROOT / "outputs" / "01a05c37-c522-7563-8846-1ea43a7a49d5" / "База пилота автоматизации критериев ТюмГУ.sqlite"


spec = importlib.util.spec_from_file_location("tyumgu_db_viewer", SERVER_PATH)
viewer = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(viewer)


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class DatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.before = checksum(DB_PATH)
        cls.database = viewer.Database(DB_PATH)

    @classmethod
    def tearDownClass(cls):
        assert checksum(DB_PATH) == cls.before, "SQLite checksum changed during read-only tests"

    def test_summary_control_counts(self):
        summary = self.database.summary()
        self.assertEqual(summary["counts"]["criteria"], 26)
        self.assertEqual(summary["counts"]["score_levels"], 78)
        self.assertEqual(summary["counts"]["instruments"], 4)
        self.assertEqual(summary["counts"]["conditions"], 6)
        self.assertEqual(summary["counts"]["effects"], 9)
        self.assertEqual(summary["counts"]["research_sources"], 35)
        self.assertEqual(summary["counts"]["criterion_source_links"], 111)
        self.assertEqual(summary["readiness"], {
            "conditional": 4,
            "not_from_recording": 2,
            "prototype_now": 20,
        })
        self.assertEqual(summary["coverage"], {
            "indirect": 3,
            "not_covered": 10,
            "partial": 13,
        })
        self.assertEqual(summary["database"]["mode"], "read-only")
        self.assertEqual(summary["database"]["quick_check"], "ok")

    def test_direct_student_data_for_criteria_24_and_25(self):
        criterion_24 = self.database.criterion("C24")
        criterion_25 = self.database.criterion("C25")
        self.assertIsNotNone(criterion_24)
        self.assertIsNotNone(criterion_25)
        required_24 = {row["code"] for row in criterion_24["data_requirements"] if row["requirement_role"] == "required"}
        required_25 = {row["code"] for row in criterion_25["data_requirements"] if row["requirement_role"] == "required"}
        self.assertEqual(required_24, {"exit_ticket"})
        self.assertEqual(required_25, {"trust_survey"})

    def test_research_sources_cover_all_criteria(self):
        sources = self.database.research_sources()
        self.assertEqual(len(sources), 35)
        self.assertEqual(len(self.database.criterion("C01")["research_sources"]), 2)
        trust_source = self.database.research_source("S29")
        self.assertIsNotNone(trust_source)
        self.assertEqual([item["code"] for item in trust_source["criteria"]], ["C25"])
        self.assertIn("S29", [item["code"] for item in self.database.search("TRUST")["sources"]])
        with self.database.session() as connection:
            self.assertEqual(
                connection.execute("SELECT COUNT(DISTINCT criterion_id) FROM criterion_research_sources").fetchone()[0],
                26,
            )

    def test_eval_2024_is_historical_and_unvalidated(self):
        instrument = self.database.instrument("LLM_EVAL")
        self.assertIsNotNone(instrument)
        version = instrument["versions"][0]
        self.assertEqual(version["version_code"], "eval-2024")
        self.assertEqual(version["lifecycle_status"], "historical")
        self.assertIn("3000", version["config_summary"])
        self.assertTrue(all(row["validation_status"] == "unvalidated" for row in instrument["coverage"]))

    def test_operational_tables_are_empty(self):
        summary = self.database.summary()
        self.assertEqual(set(summary["operational"].values()), {0})

    def test_table_whitelist_and_page_cap(self):
        with self.assertRaises(KeyError):
            self.database.table_data("criteria; DROP TABLE criteria")
        page = self.database.table_data("criterion_score_levels", limit=1000, offset=0)
        self.assertEqual(page["limit"], 100)
        self.assertEqual(page["total"], 78)
        self.assertEqual(len(page["rows"]), 78)

    def test_database_rejects_writes(self):
        connection = self.database.connect()
        try:
            with self.assertRaises(Exception):
                connection.execute("INSERT INTO experts (pseudonym) VALUES ('TEST-WRITE')")
        finally:
            connection.close()


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.before = checksum(DB_PATH)
        cls.server = viewer.create_server(DB_PATH, 0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)
        assert checksum(DB_PATH) == cls.before, "SQLite checksum changed while serving HTTP"

    def get_json(self, path: str):
        with urlopen(self.base_url + path, timeout=5) as response:
            self.assertEqual(response.headers.get_content_type(), "application/json")
            return response.status, json.loads(response.read().decode("utf-8"))

    def test_health_and_key_endpoints(self):
        status, health = self.get_json("/health")
        self.assertEqual(status, 200)
        self.assertEqual(health["status"], "ok")
        for path in (
            "/api/summary",
            "/api/criteria",
            "/api/criteria/C24",
            "/api/sources",
            "/api/sources/S29",
            "/api/instruments/LLM_EVAL",
            "/api/conditions/A4",
            "/api/effects/E8",
            "/api/tables",
            "/api/tables/criteria?limit=10&offset=0",
        ):
            status, _ = self.get_json(path)
            self.assertEqual(status, 200, path)

    def test_index_and_assets(self):
        for path, expected_type in (("/", "text/html"), ("/static/app.js", "text/javascript"), ("/assets/erd.svg", "image/svg+xml")):
            with urlopen(self.base_url + path, timeout=5) as response:
                self.assertEqual(response.status, 200)
                self.assertEqual(response.headers.get_content_type(), expected_type)
                self.assertGreater(len(response.read()), 100)

    def test_unknown_table_is_rejected(self):
        with self.assertRaises(HTTPError) as context:
            urlopen(self.base_url + "/api/tables/not_a_real_table", timeout=5)
        self.assertEqual(context.exception.code, 404)
        context.exception.close()

    def test_mutating_method_is_rejected(self):
        request = Request(self.base_url + "/api/summary", data=b"{}", method="POST")
        with self.assertRaises(HTTPError) as context:
            urlopen(request, timeout=5)
        self.assertEqual(context.exception.code, 405)
        context.exception.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
