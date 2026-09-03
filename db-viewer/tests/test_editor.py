from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[2]
VIEWER_DIR = PROJECT_ROOT / "db-viewer"
SERVER_PATH = VIEWER_DIR / "server.py"
EXPORT_PATH = VIEWER_DIR / "export_sql.py"
DB_PATH = PROJECT_ROOT / "outputs" / "01a05c37-c522-7563-8846-1ea43a7a49d5" / "База пилота автоматизации критериев ТюмГУ.sqlite"

sys.path.insert(0, str(VIEWER_DIR))


server_spec = importlib.util.spec_from_file_location("tyumgu_editor_server", SERVER_PATH)
viewer = importlib.util.module_from_spec(server_spec)
assert server_spec.loader is not None
server_spec.loader.exec_module(viewer)

export_spec = importlib.util.spec_from_file_location("tyumgu_editor_export", EXPORT_PATH)
exporter = importlib.util.module_from_spec(export_spec)
assert export_spec.loader is not None
export_spec.loader.exec_module(exporter)


class EditorDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.database_path = self.root / "working.sqlite"
        shutil.copy2(DB_PATH, self.database_path)
        self.database = viewer.Database(
            self.database_path,
            editable=True,
            backup_dir=self.root / "backups",
            journal_path=self.root / "change-log.jsonl",
        )

    def tearDown(self):
        with self.database.session() as connection:
            self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
        self.tempdir.cleanup()

    def test_all_tables_are_editable_and_views_are_not(self):
        objects = self.database.object_names()
        tables = [name for name, kind in objects.items() if kind == "table"]
        views = [name for name, kind in objects.items() if kind == "view"]
        self.assertEqual(len(tables), 38)
        self.assertEqual(len(views), 4)
        for table in tables:
            schema = self.database.table_schema(table, require_table=True)
            self.assertTrue(schema["editable"])
            self.assertTrue(schema["primary_key"])
        with self.assertRaises(viewer.EditorError) as context:
            self.database.editor_table_data("v_criterion_scale")
        self.assertEqual(context.exception.code, "view_is_read_only")

    def test_research_source_and_link_crud(self):
        source = self.database.insert_row(
            "research_sources",
            {
                "code": "S-USER-TEST",
                "citation_apa": "Пользовательский тестовый источник.",
                "verification_status": "to_review",
            },
        )["row"]
        criterion_id = self.database.criterion("C01")["id"]
        link = self.database.insert_row(
            "criterion_research_sources",
            {
                "criterion_id": criterion_id,
                "research_source_id": source["key"]["id"],
                "relation_role": "Пользовательское обоснование",
                "relevance_status": "to_review",
                "supported_claim": "Проверить применимость к критерию.",
            },
        )["row"]
        updated = self.database.update_row(
            "criterion_research_sources",
            link["key"],
            {"relevance_status": "confirmed"},
            link["etag"],
        )["row"]
        self.assertEqual(updated["values"]["relevance_status"], "confirmed")

    def test_single_key_crud_null_empty_and_stale_etag(self):
        created = self.database.insert_row(
            "experts",
            {"pseudonym": "EX-TEST", "qualification": "Методист", "active": 1, "notes": None},
        )["row"]
        self.assertIsNone(created["values"]["notes"])
        updated = self.database.update_row(
            "experts", created["key"], {"notes": ""}, created["etag"]
        )["row"]
        self.assertEqual(updated["values"]["notes"], "")
        with self.assertRaises(viewer.EditorError) as context:
            self.database.update_row("experts", created["key"], {"notes": "old"}, created["etag"])
        self.assertEqual(context.exception.code, "stale_row")
        preview = self.database.delete_preview("experts", updated["key"], updated["etag"])
        result = self.database.delete_row(
            "experts", updated["key"], updated["etag"], preview["confirmation_token"]
        )
        self.assertTrue(result["deleted"])
        self.assertEqual(len(list((self.root / "backups").glob("*.sqlite"))), 1)
        self.assertEqual([item["action"] for item in reversed(self.database.history())], ["insert", "update", "delete"])

    def test_composite_key_crud(self):
        with self.database.session() as connection:
            study_id = connection.execute("SELECT id FROM studies ORDER BY id LIMIT 1").fetchone()[0]
        lesson = self.database.insert_row(
            "lessons",
            {"public_id": "LESSON-COMPOSITE", "study_id": study_id, "status": "planned"},
        )["row"]
        split = self.database.insert_row(
            "dataset_splits",
            {"study_id": study_id, "code": "test-split", "name": "Test", "purpose": "CRUD test"},
        )["row"]
        link = self.database.insert_row(
            "lesson_splits",
            {"lesson_id": lesson["key"]["id"], "split_id": split["key"]["id"]},
        )["row"]
        self.assertEqual(set(link["key"]), {"lesson_id", "split_id"})
        changed = self.database.update_row(
            "lesson_splits", link["key"], {"assigned_at": "2026-09-03T00:00:00Z"}, link["etag"]
        )["row"]
        preview = self.database.delete_preview("lesson_splits", changed["key"], changed["etag"])
        self.database.delete_row(
            "lesson_splits", changed["key"], changed["etag"], preview["confirmation_token"]
        )
        page = self.database.editor_table_data("lesson_splits", limit=100)
        self.assertFalse(any(item["key"] == changed["key"] for item in page["rows"]))

    def test_constraints_json_and_foreign_key_are_enforced(self):
        with self.assertRaises(viewer.EditorError) as context:
            self.database.insert_row(
                "evaluation_runs",
                {
                    "public_id": "RUN-BAD-JSON",
                    "lesson_id": 999999,
                    "condition_id": 999999,
                    "status": "queued",
                    "configuration_json": "{bad",
                },
            )
        self.assertEqual(context.exception.code, "invalid_json")
        with self.assertRaises(Exception):
            self.database.insert_row(
                "lessons",
                {"public_id": "LESSON-BAD-FK", "study_id": 999999, "status": "planned"},
            )
        with self.assertRaises(Exception):
            self.database.insert_row(
                "experts",
                {"pseudonym": "EX-BAD-ENUM", "active": 4},
            )

    def test_delete_preview_requires_typed_confirmation_for_dependencies(self):
        with self.database.session() as connection:
            study_id = connection.execute("SELECT id FROM studies ORDER BY id LIMIT 1").fetchone()[0]
            data_type_id = connection.execute("SELECT id FROM data_types ORDER BY id LIMIT 1").fetchone()[0]
        lesson = self.database.insert_row(
            "lessons",
            {"public_id": "LESSON-CASCADE", "study_id": study_id, "status": "planned"},
        )["row"]
        self.database.insert_row(
            "lesson_artifacts",
            {
                "public_id": "ARTIFACT-CASCADE",
                "lesson_id": lesson["key"]["id"],
                "data_type_id": data_type_id,
                "storage_uri": "local://test",
            },
        )
        preview = self.database.delete_preview("lessons", lesson["key"], lesson["etag"])
        self.assertGreaterEqual(preview["dependent_rows"], 1)
        with self.assertRaises(viewer.EditorError) as context:
            self.database.delete_row(
                "lessons", lesson["key"], lesson["etag"], preview["confirmation_token"]
            )
        self.assertEqual(context.exception.code, "typed_confirmation_required")
        self.database.delete_row(
            "lessons",
            lesson["key"],
            lesson["etag"],
            preview["confirmation_token"],
            confirmation_text="lessons",
        )
        with self.database.session() as connection:
            count = connection.execute("SELECT COUNT(*) FROM lesson_artifacts WHERE public_id='ARTIFACT-CASCADE'").fetchone()[0]
        self.assertEqual(count, 0)

    def test_sql_export_recreates_current_database(self):
        self.database.insert_row("experts", {"pseudonym": "EX-EXPORT", "active": 1})
        dump = exporter.export_database(self.database_path, self.root / "snapshot.sql")
        rebuilt = self.root / "rebuilt.sqlite"
        connection = __import__("sqlite3").connect(rebuilt)
        try:
            connection.executescript(dump.read_text(encoding="utf-8"))
            self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM experts WHERE pseudonym='EX-EXPORT'").fetchone()[0], 1)
        finally:
            connection.close()


class EditorHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tempdir = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tempdir.name)
        cls.database_path = cls.root / "working.sqlite"
        shutil.copy2(DB_PATH, cls.database_path)
        cls.server = viewer.create_server(
            cls.database_path,
            0,
            edit=True,
            backup_dir=cls.root / "backups",
            journal_path=cls.root / "change-log.jsonl",
        )
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)
        cls.tempdir.cleanup()

    def json_request(self, path: str, method: str = "GET", body=None, token: str | None = None, origin: bool = True):
        headers = {"Accept": "application/json"}
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if token:
            headers["X-CSRF-Token"] = token
        if origin:
            headers["Origin"] = self.base_url
        request = Request(self.base_url + path, data=data, headers=headers, method=method)
        with urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))

    def test_status_schema_and_csrf_protected_crud(self):
        _, status = self.json_request("/api/editor/status", origin=False)
        self.assertTrue(status["enabled"])
        token = status["csrf_token"]
        _, table = self.json_request("/api/editor/tables/experts?limit=10", origin=False)
        self.assertEqual(table["schema"]["primary_key"], ["id"])
        with self.assertRaises(HTTPError) as context:
            self.json_request(
                "/api/editor/tables/experts/rows",
                method="POST",
                body={"values": {"pseudonym": "EX-CSRF", "active": 1}},
                token=token,
                origin=False,
            )
        self.assertEqual(context.exception.code, 403)
        context.exception.close()
        code, created = self.json_request(
            "/api/editor/tables/experts/rows",
            method="POST",
            body={"values": {"pseudonym": "EX-HTTP", "active": 1}},
            token=token,
        )
        self.assertEqual(code, 201)
        row = created["row"]
        _, updated = self.json_request(
            "/api/editor/tables/experts/rows",
            method="PATCH",
            body={"key": row["key"], "values": {"notes": "HTTP"}, "etag": row["etag"]},
            token=token,
        )
        row = updated["row"]
        _, preview = self.json_request(
            "/api/editor/tables/experts/delete-preview",
            method="POST",
            body={"key": row["key"], "etag": row["etag"]},
            token=token,
        )
        code, deleted = self.json_request(
            "/api/editor/tables/experts/rows",
            method="DELETE",
            body={
                "key": row["key"],
                "etag": row["etag"],
                "confirmation_token": preview["confirmation_token"],
            },
            token=token,
        )
        self.assertEqual(code, 200)
        self.assertTrue(deleted["deleted"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
