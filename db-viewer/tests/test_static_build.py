from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
VIEWER_DIR = PROJECT_ROOT / "db-viewer"
BUILD_PATH = VIEWER_DIR / "build_static.py"
DB_PATH = PROJECT_ROOT / "outputs" / "01a05c37-c522-7563-8846-1ea43a7a49d5" / "База пилота автоматизации критериев ТюмГУ.sqlite"

sys.path.insert(0, str(VIEWER_DIR))
spec = importlib.util.spec_from_file_location("tyumgu_static_builder", BUILD_PATH)
builder = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(builder)


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class StaticBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.before = checksum(DB_PATH)
        cls.tempdir = tempfile.TemporaryDirectory()
        cls.site = Path(cls.tempdir.name) / "site"
        builder.build_site(DB_PATH, cls.site)

    @classmethod
    def tearDownClass(cls):
        cls.tempdir.cleanup()
        assert checksum(DB_PATH) == cls.before, "SQLite checksum changed during static export"

    def read_json(self, relative: str):
        return json.loads((self.site / relative).read_text(encoding="utf-8"))

    def test_pages_entrypoints_and_relative_assets(self):
        for relative in ("index.html", "404.html", ".nojekyll", "static/app.js", "static/styles.css", "static/config.js", "assets/erd.svg", "assets/erd.mmd"):
            self.assertTrue((self.site / relative).is_file(), relative)
        index = (self.site / "index.html").read_text(encoding="utf-8")
        self.assertIn('href="./static/styles.css?v=20260903-methods"', index)
        self.assertIn('src="./static/config.js?v=20260903-methods"', index)
        self.assertIn('src="./static/app.js?v=20260903-methods"', index)
        self.assertIn('mode: "static"', (self.site / "static/config.js").read_text(encoding="utf-8"))

    def test_snapshot_control_counts_and_details(self):
        summary = self.read_json("data/summary.json")
        self.assertEqual(summary["counts"]["criteria"], 26)
        self.assertEqual(summary["counts"]["score_levels"], 78)
        self.assertEqual(summary["counts"]["instruments"], 4)
        self.assertEqual(summary["counts"]["conditions"], 6)
        self.assertEqual(summary["counts"]["effects"], 9)
        self.assertEqual(summary["counts"]["research_sources"], 47)
        self.assertEqual(summary["counts"]["criterion_source_links"], 111)
        self.assertEqual(summary["counts"]["method_source_links"], 24)
        self.assertEqual(summary["database"]["mode"], "static_snapshot")
        self.assertTrue((self.site / "data/criteria/C24.json").is_file())
        self.assertTrue((self.site / "data/instruments/LLM_EVAL.json").is_file())
        self.assertTrue((self.site / "data/conditions/A4.json").is_file())
        self.assertTrue((self.site / "data/effects/E8.json").is_file())
        self.assertTrue((self.site / "data/sources/S29.json").is_file())
        source = self.read_json("data/sources/S29.json")
        self.assertEqual([item["code"] for item in source["criteria"]], ["C25"])
        effect = self.read_json("data/effects/E9.json")
        self.assertEqual(effect["method_name"], "Повторяемость идентичных прогонов")
        self.assertTrue(effect["literature_sources"])
        self.assertTrue((self.site / "data/sources/S46.json").is_file())

    def test_all_table_rows_are_exported(self):
        table = self.read_json("data/tables/effect_check_criteria.json")
        self.assertEqual(table["total"], 214)
        self.assertEqual(len(table["rows"]), 214)
        empty = self.read_json("data/tables/effect_results.json")
        self.assertIsNone(empty["total"])
        self.assertEqual(empty["rows"], [])
        self.assertTrue(empty["restricted"])
        self.assertEqual(empty["visibility"], "local_only")

    def test_operational_tables_do_not_publish_rows_or_counts(self):
        summary = self.read_json("data/summary.json")
        self.assertEqual(summary["operational_visibility"], "local_only")
        self.assertEqual(set(summary["operational"].values()), {None})
        index = self.read_json("data/tables/index.json")
        by_name = {item["name"]: item for item in index["items"]}
        for name in builder.PUBLIC_SCHEMA_ONLY_TABLES:
            self.assertIsNone(by_name[name]["row_count"])
            self.assertTrue(by_name[name]["restricted"])

    def test_populated_operational_rows_are_excluded(self):
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            database_path = root / "working.sqlite"
            shutil.copy2(DB_PATH, database_path)
            database = builder.Database(
                database_path,
                editable=True,
                backup_dir=root / "backups",
                journal_path=root / "change-log.jsonl",
            )
            database.insert_row("experts", {"pseudonym": "EX-PRIVATE-STATIC-TEST", "active": 1})
            site = root / "site"
            builder.build_site(database_path, site)
            experts = json.loads((site / "data" / "tables" / "experts.json").read_text(encoding="utf-8"))
            self.assertEqual(experts["rows"], [])
            self.assertIsNone(experts["total"])
            exported_json = "\n".join(path.read_text(encoding="utf-8") for path in (site / "data").rglob("*.json"))
            self.assertNotIn("EX-PRIVATE-STATIC-TEST", exported_json)

    def test_snapshot_contains_no_absolute_workspace_path_or_token(self):
        json_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (self.site / "data").rglob("*.json")
        )
        self.assertNotIn(str(PROJECT_ROOT), json_text)
        self.assertIsNone(re.search(r"sk-[A-Za-z0-9_-]{20,}", json_text))

    def test_refuses_to_replace_unrelated_directory(self):
        with tempfile.TemporaryDirectory() as tempdir:
            target = Path(tempdir) / "existing"
            target.mkdir()
            (target / "keep.txt").write_text("user file", encoding="utf-8")
            with self.assertRaises(ValueError):
                builder.build_site(DB_PATH, target)
            self.assertEqual((target / "keep.txt").read_text(encoding="utf-8"), "user file")


if __name__ == "__main__":
    unittest.main(verbosity=2)
