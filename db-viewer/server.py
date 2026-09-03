#!/usr/bin/env python3
"""Local viewer and opt-in editor for the TyumGU pilot SQLite database."""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import re
import secrets
import sqlite3
import sys
import threading
import webbrowser
from contextlib import contextmanager
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlparse


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "01a05c37-c522-7563-8846-1ea43a7a49d5"
DEFAULT_DB = OUTPUT_DIR / "База пилота автоматизации критериев ТюмГУ.sqlite"
DEFAULT_ERD = OUTPUT_DIR / "ERD базы пилота автоматизации критериев ТюмГУ.svg"
DEFAULT_MMD = OUTPUT_DIR / "ERD базы пилота автоматизации критериев ТюмГУ.mmd"
STATIC_DIR = Path(__file__).resolve().parent / "static"
VAR_DIR = Path(__file__).resolve().parent / "var"
DEFAULT_BACKUP_DIR = VAR_DIR / "backups"
DEFAULT_JOURNAL = VAR_DIR / "change-log.jsonl"
STATIC_BUILD_INFO = PROJECT_ROOT / "docs" / "data" / "build.json"
MAX_PAGE_SIZE = 100
MAX_JSON_BODY = 1024 * 1024

PUBLIC_SCHEMA_ONLY_TABLES = {
    "experts",
    "instructors",
    "student_groups",
    "lessons",
    "dataset_splits",
    "lesson_splits",
    "lesson_artifacts",
    "evaluation_runs",
    "run_instruments",
    "run_inputs",
    "criterion_evaluations",
    "evidence_fragments",
    "evaluation_reviews",
    "effect_results",
    "criterion_decisions",
}


def _dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _json_safe(value: Any) -> Any:
    if isinstance(value, bytes):
        return {"bytes_hex": value.hex()}
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


class EditorError(Exception):
    """Expected editor error that can be returned to the browser."""

    def __init__(self, status: HTTPStatus, code: str, detail: str, **extra: Any):
        super().__init__(detail)
        self.status = status
        self.code = code
        self.detail = detail
        self.extra = extra


class Database:
    """Query repository with an explicit, local-only editable mode."""

    def __init__(
        self,
        path: Path,
        editable: bool = False,
        backup_dir: Path = DEFAULT_BACKUP_DIR,
        journal_path: Path = DEFAULT_JOURNAL,
    ):
        self.path = path.resolve()
        if not self.path.is_file():
            raise FileNotFoundError(f"SQLite database not found: {self.path}")
        self.editable = editable
        self.backup_dir = backup_dir.resolve()
        self.journal_path = journal_path.resolve()
        self.startup_sha256 = self.file_sha256()
        self.backup_path: Path | None = None
        self.editor_token = secrets.token_urlsafe(32)
        self._write_lock = threading.RLock()

    def file_sha256(self) -> str:
        digest = hashlib.sha256()
        with self.path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def connect(self, force_read_only: bool = False) -> sqlite3.Connection:
        uri_path = quote(self.path.as_posix(), safe="/:")
        read_only = force_read_only or not self.editable
        mode = "ro" if read_only else "rw"
        connection = sqlite3.connect(f"file:{uri_path}?mode={mode}", uri=True, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        if read_only:
            connection.execute("PRAGMA query_only = ON")
        return connection

    @contextmanager
    def session(self):
        connection = self.connect()
        try:
            yield connection
        finally:
            connection.close()

    def object_names(self) -> dict[str, str]:
        with self.session() as connection:
            rows = connection.execute(
                """SELECT name, type
                   FROM sqlite_schema
                   WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%'
                   ORDER BY type, name"""
            ).fetchall()
        return {row["name"]: row["type"] for row in rows}

    @staticmethod
    def _quoted_identifier(name: str, allowed: set[str]) -> str:
        if name not in allowed:
            raise KeyError(name)
        return '"' + name.replace('"', '""') + '"'

    def summary(self) -> dict[str, Any]:
        with self.session() as connection:
            counts = dict(
                connection.execute(
                    """SELECT 'criteria' AS key, COUNT(*) AS value FROM criteria
                       UNION ALL SELECT 'score_levels', COUNT(*) FROM criterion_score_levels
                       UNION ALL SELECT 'instruments', COUNT(*) FROM instruments
                       UNION ALL SELECT 'conditions', COUNT(*) FROM comparison_conditions
                       UNION ALL SELECT 'effects', COUNT(*) FROM effects
                       UNION ALL SELECT 'research_sources', COUNT(*) FROM research_sources
                       UNION ALL SELECT 'criterion_source_links', COUNT(*) FROM criterion_research_sources
                       UNION ALL SELECT 'tables', COUNT(*) FROM sqlite_schema
                           WHERE type='table' AND name NOT LIKE 'sqlite_%'
                       UNION ALL SELECT 'views', COUNT(*) FROM sqlite_schema
                           WHERE type='view' AND name NOT LIKE 'sqlite_%'"""
                ).fetchall()
            )
            readiness = dict(
                connection.execute(
                    "SELECT readiness_status, COUNT(*) FROM study_criteria GROUP BY readiness_status"
                ).fetchall()
            )
            coverage = dict(
                connection.execute(
                    "SELECT platform_coverage_status, COUNT(*) FROM study_criteria GROUP BY platform_coverage_status"
                ).fetchall()
            )
            study = dict(
                connection.execute(
                    "SELECT code, name, objective, status, design_version FROM studies ORDER BY id LIMIT 1"
                ).fetchone()
            )
            operational = dict(
                connection.execute(
                    """SELECT 'lessons' AS key, COUNT(*) AS value FROM lessons
                       UNION ALL SELECT 'runs', COUNT(*) FROM evaluation_runs
                       UNION ALL SELECT 'evaluations', COUNT(*) FROM criterion_evaluations
                       UNION ALL SELECT 'evidence', COUNT(*) FROM evidence_fragments
                       UNION ALL SELECT 'results', COUNT(*) FROM effect_results"""
                ).fetchall()
            )
            quick_check = connection.execute("PRAGMA quick_check").fetchone()[0]
        return {
            "study": study,
            "counts": counts,
            "readiness": readiness,
            "coverage": coverage,
            "operational": operational,
            "database": {
                "file": self.path.name,
                "quick_check": quick_check,
                "mode": "editable" if self.editable else "read-only",
            },
        }

    def criteria(self, filters: dict[str, str] | None = None) -> list[dict[str, Any]]:
        filters = filters or {}
        conditions: list[str] = []
        parameters: list[Any] = []
        if filters.get("block"):
            conditions.append("c.block_name = ?")
            parameters.append(filters["block"])
        if filters.get("readiness"):
            conditions.append("sc.readiness_status = ?")
            parameters.append(filters["readiness"])
        if filters.get("coverage"):
            conditions.append("sc.platform_coverage_status = ?")
            parameters.append(filters["coverage"])
        if filters.get("q"):
            conditions.append("(c.name LIKE ? OR c.code LIKE ? OR c.block_name LIKE ?)")
            needle = f"%{filters['q']}%"
            parameters.extend([needle, needle, needle])
        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        query = f"""SELECT
                c.id, c.number, c.code, c.block_name, c.subblock_name, c.name,
                sc.readiness_status, sc.platform_coverage_status, sc.notes,
                (SELECT COUNT(*) FROM criterion_data_requirements AS cdr WHERE cdr.criterion_id=c.id) AS data_requirements_count,
                (SELECT COUNT(*) FROM instrument_version_criteria AS ivc WHERE ivc.criterion_id=c.id) AS instrument_links_count,
                (SELECT COUNT(*) FROM criterion_research_sources AS crs WHERE crs.criterion_id=c.id) AS research_sources_count
            FROM criteria AS c
            JOIN study_criteria AS sc ON sc.criterion_id=c.id
            {where}
            ORDER BY c.number"""
        with self.session() as connection:
            return _dicts(connection.execute(query, parameters).fetchall())

    def criterion(self, code: str) -> dict[str, Any] | None:
        with self.session() as connection:
            row = connection.execute(
                """SELECT c.*, sc.readiness_status, sc.platform_coverage_status, sc.notes,
                          sd.title AS source_title, sd.relative_path AS source_path
                   FROM criteria AS c
                   JOIN study_criteria AS sc ON sc.criterion_id=c.id
                   JOIN source_documents AS sd ON sd.id=c.source_document_id
                   WHERE c.code=?""",
                (code,),
            ).fetchone()
            if row is None:
                return None
            criterion_id = row["id"]
            levels = _dicts(
                connection.execute(
                    "SELECT score, description FROM criterion_score_levels WHERE criterion_id=? ORDER BY score DESC",
                    (criterion_id,),
                ).fetchall()
            )
            data_requirements = _dicts(
                connection.execute(
                    """SELECT dt.code, dt.name, dt.category, cdr.requirement_role, cdr.reason
                       FROM criterion_data_requirements AS cdr
                       JOIN data_types AS dt ON dt.id=cdr.data_type_id
                       WHERE cdr.criterion_id=?
                       ORDER BY CASE cdr.requirement_role WHEN 'required' THEN 0 WHEN 'reference' THEN 1 ELSE 2 END, dt.name""",
                    (criterion_id,),
                ).fetchall()
            )
            instrument_coverage = _dicts(
                connection.execute(
                    """SELECT i.code AS instrument_code, i.name AS instrument_name, i.instrument_kind,
                              v.version_code, v.version_name, v.lifecycle_status, v.methodology_status,
                              COALESCE(ivc.coverage_status, 'not_mapped') AS coverage_status,
                              COALESCE(ivc.validation_status, 'not_documented') AS validation_status,
                              ivc.output_type, ivc.notes
                       FROM instrument_versions AS v
                       JOIN instruments AS i ON i.id=v.instrument_id
                       LEFT JOIN instrument_version_criteria AS ivc
                           ON ivc.instrument_version_id=v.id AND ivc.criterion_id=?
                       ORDER BY i.id, v.id""",
                    (criterion_id,),
                ).fetchall()
            )
            effects = _dicts(
                connection.execute(
                    """SELECT e.code, e.name, ec.code AS check_code, vm.code AS method_code,
                              vm.name AS method_name, ecc.scope_role
                       FROM effect_check_criteria AS ecc
                       JOIN effect_checks AS ec ON ec.id=ecc.effect_check_id
                       JOIN effects AS e ON e.id=ec.effect_id
                       JOIN verification_methods AS vm ON vm.id=ec.verification_method_id
                       WHERE ecc.criterion_id=?
                       ORDER BY e.effect_order""",
                    (criterion_id,),
                ).fetchall()
            )
            research_sources = _dicts(
                connection.execute(
                    """SELECT rs.id, rs.code, rs.citation_apa, rs.doi, rs.url,
                              rs.study_type, rs.evidence_summary, rs.access_notes,
                              rs.evidence_role, rs.verification_status, rs.registry_checked_on,
                              crs.id AS link_id, crs.relation_role, crs.relevance_status,
                              crs.supported_claim, crs.source_locator, crs.notes AS link_notes
                       FROM criterion_research_sources AS crs
                       JOIN research_sources AS rs ON rs.id=crs.research_source_id
                       WHERE crs.criterion_id=?
                       ORDER BY rs.code""",
                    (criterion_id,),
                ).fetchall()
            )
        result = dict(row)
        result.update(
            {
                "levels": levels,
                "data_requirements": data_requirements,
                "instrument_coverage": instrument_coverage,
                "effects": effects,
                "research_sources": research_sources,
            }
        )
        return result

    def research_sources(self, query: str = "") -> list[dict[str, Any]]:
        where = ""
        parameters: list[Any] = []
        if query:
            needle = f"%{query[:100]}%"
            where = """WHERE rs.code LIKE ? OR rs.citation_apa LIKE ? OR rs.doi LIKE ?
                       OR rs.study_type LIKE ? OR rs.evidence_role LIKE ?"""
            parameters = [needle] * 5
        with self.session() as connection:
            return _dicts(
                connection.execute(
                    f"""SELECT rs.*, COALESCE(rs.study_type, rs.citation_apa) AS name,
                               COUNT(DISTINCT crs.criterion_id) AS criteria_count
                        FROM research_sources AS rs
                        LEFT JOIN criterion_research_sources AS crs ON crs.research_source_id=rs.id
                        {where}
                        GROUP BY rs.id
                        ORDER BY CAST(SUBSTR(rs.code, 2) AS INTEGER), rs.code""",
                    parameters,
                ).fetchall()
            )

    def research_source(self, code: str) -> dict[str, Any] | None:
        with self.session() as connection:
            row = connection.execute(
                """SELECT rs.*, sd.title AS provenance_title, sd.relative_path AS provenance_path
                   FROM research_sources AS rs
                   LEFT JOIN source_documents AS sd ON sd.id=rs.provenance_document_id
                   WHERE rs.code=?""",
                (code,),
            ).fetchone()
            if row is None:
                return None
            criteria = _dicts(
                connection.execute(
                    """SELECT c.id, c.code, c.number, c.name, c.block_name,
                              crs.id AS link_id, crs.relation_role, crs.relevance_status,
                              crs.supported_claim, crs.source_locator, crs.notes
                       FROM criterion_research_sources AS crs
                       JOIN criteria AS c ON c.id=crs.criterion_id
                       WHERE crs.research_source_id=?
                       ORDER BY c.number""",
                    (row["id"],),
                ).fetchall()
            )
        result = dict(row)
        result["criteria"] = criteria
        return result

    def instruments(self) -> list[dict[str, Any]]:
        with self.session() as connection:
            return _dicts(
                connection.execute(
                    """SELECT i.*,
                              (SELECT COUNT(*) FROM instrument_versions AS v WHERE v.instrument_id=i.id) AS versions_count,
                              (SELECT COUNT(DISTINCT ivc.criterion_id)
                               FROM instrument_versions AS v
                               JOIN instrument_version_criteria AS ivc ON ivc.instrument_version_id=v.id
                               WHERE v.instrument_id=i.id) AS criteria_count
                       FROM instruments AS i
                       ORDER BY i.id"""
                ).fetchall()
            )

    def instrument(self, code: str) -> dict[str, Any] | None:
        with self.session() as connection:
            instrument_row = connection.execute("SELECT * FROM instruments WHERE code=?", (code,)).fetchone()
            if instrument_row is None:
                return None
            instrument_id = instrument_row["id"]
            versions = _dicts(
                connection.execute(
                    """SELECT v.*, sd.title AS source_title, sd.relative_path AS source_path
                       FROM instrument_versions AS v
                       LEFT JOIN source_documents AS sd ON sd.id=v.source_document_id
                       WHERE v.instrument_id=? ORDER BY v.id""",
                    (instrument_id,),
                ).fetchall()
            )
            version_ids = [row["id"] for row in versions]
            inputs: list[dict[str, Any]] = []
            coverage: list[dict[str, Any]] = []
            if version_ids:
                placeholders = ",".join("?" for _ in version_ids)
                inputs = _dicts(
                    connection.execute(
                        f"""SELECT ivdt.instrument_version_id, dt.code, dt.name, dt.category,
                                   ivdt.requirement_role, ivdt.purpose
                            FROM instrument_version_data_types AS ivdt
                            JOIN data_types AS dt ON dt.id=ivdt.data_type_id
                            WHERE ivdt.instrument_version_id IN ({placeholders})
                            ORDER BY ivdt.instrument_version_id, dt.name""",
                        version_ids,
                    ).fetchall()
                )
                coverage = _dicts(
                    connection.execute(
                        f"""SELECT ivc.instrument_version_id, c.code, c.number, c.name,
                                   ivc.coverage_status, ivc.validation_status, ivc.output_type, ivc.notes
                            FROM instrument_version_criteria AS ivc
                            JOIN criteria AS c ON c.id=ivc.criterion_id
                            WHERE ivc.instrument_version_id IN ({placeholders})
                            ORDER BY ivc.instrument_version_id, c.number""",
                        version_ids,
                    ).fetchall()
                )
        result = dict(instrument_row)
        result.update({"versions": versions, "inputs": inputs, "coverage": coverage})
        return result

    def conditions(self) -> list[dict[str, Any]]:
        with self.session() as connection:
            conditions = _dicts(
                connection.execute("SELECT * FROM comparison_conditions ORDER BY condition_order").fetchall()
            )
            for condition in conditions:
                condition["instruments"] = _dicts(
                    connection.execute(
                        """SELECT i.code, i.name, i.instrument_kind, ci.role, ci.notes
                           FROM condition_instruments AS ci
                           JOIN instruments AS i ON i.id=ci.instrument_id
                           WHERE ci.condition_id=? ORDER BY i.id""",
                        (condition["id"],),
                    ).fetchall()
                )
                condition["data_types"] = _dicts(
                    connection.execute(
                        """SELECT dt.code, dt.name, dt.category, cdt.requirement_role, cdt.purpose
                           FROM condition_data_types AS cdt
                           JOIN data_types AS dt ON dt.id=cdt.data_type_id
                           WHERE cdt.condition_id=? ORDER BY dt.id""",
                        (condition["id"],),
                    ).fetchall()
                )
        return conditions

    def condition(self, code: str) -> dict[str, Any] | None:
        conditions = self.conditions()
        selected = next((item for item in conditions if item["code"] == code), None)
        if selected is None:
            return None
        with self.session() as connection:
            selected["effect_checks"] = _dicts(
                connection.execute(
                    """SELECT e.code AS effect_code, e.name AS effect_name, ec.code AS check_code,
                              ecc.role, ecc.notes, vm.code AS method_code, vm.name AS method_name
                       FROM effect_check_conditions AS ecc
                       JOIN effect_checks AS ec ON ec.id=ecc.effect_check_id
                       JOIN effects AS e ON e.id=ec.effect_id
                       JOIN verification_methods AS vm ON vm.id=ec.verification_method_id
                       WHERE ecc.condition_id=? ORDER BY e.effect_order""",
                    (selected["id"],),
                ).fetchall()
            )
        return selected

    def effects(self) -> list[dict[str, Any]]:
        with self.session() as connection:
            effects = _dicts(
                connection.execute(
                    """SELECT e.*, ec.id AS effect_check_id, ec.code AS check_code,
                              ec.unit_of_analysis, ec.comparison_description, ec.success_rule,
                              vm.code AS method_code, vm.name AS method_name, vm.description AS method_description,
                              vm.metrics, vm.procedure
                       FROM effects AS e
                       JOIN effect_checks AS ec ON ec.effect_id=e.id
                       JOIN verification_methods AS vm ON vm.id=ec.verification_method_id
                       ORDER BY e.effect_order"""
                ).fetchall()
            )
            for effect in effects:
                effect["conditions"] = _dicts(
                    connection.execute(
                        """SELECT cc.code, cc.name, ecc.role, ecc.notes
                           FROM effect_check_conditions AS ecc
                           JOIN comparison_conditions AS cc ON cc.id=ecc.condition_id
                           WHERE ecc.effect_check_id=? ORDER BY cc.condition_order""",
                        (effect["effect_check_id"],),
                    ).fetchall()
                )
                effect["data_types"] = _dicts(
                    connection.execute(
                        """SELECT dt.code, dt.name, ecd.role, ecd.notes
                           FROM effect_check_data_types AS ecd
                           JOIN data_types AS dt ON dt.id=ecd.data_type_id
                           WHERE ecd.effect_check_id=? ORDER BY dt.id""",
                        (effect["effect_check_id"],),
                    ).fetchall()
                )
                effect["criteria"] = _dicts(
                    connection.execute(
                        """SELECT c.code, c.number, c.name, ecc.scope_role
                           FROM effect_check_criteria AS ecc
                           JOIN criteria AS c ON c.id=ecc.criterion_id
                           WHERE ecc.effect_check_id=? ORDER BY c.number""",
                        (effect["effect_check_id"],),
                    ).fetchall()
                )
        return effects

    def effect(self, code: str) -> dict[str, Any] | None:
        return next((item for item in self.effects() if item["code"] == code), None)

    def search(self, query: str) -> dict[str, list[dict[str, Any]]]:
        needle = query.strip().casefold()[:100]
        if not needle:
            return {"criteria": [], "sources": [], "instruments": [], "conditions": [], "effects": []}

        def matches(item: dict[str, Any], fields: tuple[str, ...]) -> bool:
            return any(needle in str(item.get(field) or "").casefold() for field in fields)

        criteria = [
            item for item in self.criteria()
            if matches(item, ("code", "name", "block_name", "subblock_name"))
        ][:8]
        sources = [
            item for item in self.research_sources()
            if matches(item, ("code", "citation_apa", "doi", "study_type", "evidence_role"))
        ][:8]
        instruments = [
            item for item in self.instruments()
            if matches(item, ("code", "name", "provider", "description"))
        ][:8]
        conditions = [
            item for item in self.conditions()
            if matches(item, ("code", "name", "description"))
        ][:8]
        effects = [
            item for item in self.effects()
            if matches(item, ("code", "name", "hypothesis", "method_code", "method_name", "metrics"))
        ][:8]
        return {"criteria": criteria, "sources": sources, "instruments": instruments, "conditions": conditions, "effects": effects}

    def tables(self) -> list[dict[str, Any]]:
        objects = self.object_names()
        result = []
        with self.session() as connection:
            for name, kind in objects.items():
                identifier = self._quoted_identifier(name, set(objects))
                count = connection.execute(f"SELECT COUNT(*) FROM {identifier}").fetchone()[0]
                columns = connection.execute(f"PRAGMA table_info({identifier})").fetchall()
                result.append(
                    {
                        "name": name,
                        "kind": kind,
                        "row_count": count,
                        "column_count": len(columns),
                        "empty": count == 0,
                    }
                )
        return result

    def table_data(self, name: str, limit: int = 50, offset: int = 0, query: str = "") -> dict[str, Any]:
        objects = self.object_names()
        allowed = set(objects)
        identifier = self._quoted_identifier(name, allowed)
        limit = max(1, min(int(limit), MAX_PAGE_SIZE))
        offset = max(0, int(offset))
        with self.session() as connection:
            column_rows = connection.execute(f"PRAGMA table_info({identifier})").fetchall()
            columns = [dict(row) for row in column_rows]
            column_names = [row["name"] for row in column_rows]
            where = ""
            parameters: list[Any] = []
            if query and column_names:
                clauses = []
                for column in column_names:
                    quoted_column = self._quoted_identifier(column, set(column_names))
                    clauses.append(f"CAST({quoted_column} AS TEXT) LIKE ?")
                    parameters.append(f"%{query[:100]}%")
                where = " WHERE " + " OR ".join(clauses)
            total = connection.execute(
                f"SELECT COUNT(*) FROM {identifier}{where}", parameters
            ).fetchone()[0]
            order_by = ""
            if column_names:
                preferred = next(
                    (column for column in ("number", "id", "code") if column in column_names),
                    column_names[0],
                )
                order_by = " ORDER BY " + self._quoted_identifier(preferred, set(column_names))
            rows = connection.execute(
                f"SELECT * FROM {identifier}{where}{order_by} LIMIT ? OFFSET ?",
                [*parameters, limit, offset],
            ).fetchall()
        return {
            "name": name,
            "kind": objects[name],
            "columns": columns,
            "rows": _dicts(rows),
            "total": total,
            "limit": limit,
            "offset": offset,
            "query": query,
        }

    @staticmethod
    def _parse_enum_options(create_sql: str, column_name: str) -> list[Any]:
        name = re.escape(column_name)
        pattern = re.compile(rf"\b{name}\b\s+IN\s*\(([^)]*)\)", re.IGNORECASE)
        match = pattern.search(create_sql)
        if not match:
            return []
        values: list[Any] = []
        for token in match.group(1).split(","):
            token = token.strip()
            if len(token) >= 2 and token[0] == token[-1] == "'":
                values.append(token[1:-1].replace("''", "'"))
            elif re.fullmatch(r"-?\d+", token):
                values.append(int(token))
            elif re.fullmatch(r"-?\d+(?:\.\d+)?", token):
                values.append(float(token))
        return values

    def table_schema(
        self,
        name: str,
        *,
        require_table: bool = False,
        connection: sqlite3.Connection | None = None,
    ) -> dict[str, Any]:
        owns_connection = connection is None
        if owns_connection:
            connection = self.connect()
        assert connection is not None
        try:
            schema_row = connection.execute(
                "SELECT name, type, sql FROM sqlite_schema WHERE name=? AND type IN ('table', 'view')",
                (name,),
            ).fetchone()
            if schema_row is None or name.startswith("sqlite_"):
                raise EditorError(HTTPStatus.NOT_FOUND, "unknown_table", "Таблица не найдена")
            if require_table and schema_row["type"] != "table":
                raise EditorError(
                    HTTPStatus.METHOD_NOT_ALLOWED,
                    "view_is_read_only",
                    "Представления доступны только для чтения",
                )
            identifier = self._quoted_identifier(name, {name})
            raw_columns = _dicts(connection.execute(f"PRAGMA table_info({identifier})").fetchall())
            create_sql = schema_row["sql"] or ""
            primary_key = [
                row["name"]
                for row in sorted(raw_columns, key=lambda row: row["pk"] or 999)
                if row["pk"]
            ]
            single_integer_pk = len(primary_key) == 1 and next(
                (row for row in raw_columns if row["name"] == primary_key[0]), {}
            ).get("type", "").upper() == "INTEGER"
            foreign_keys = _dicts(connection.execute(f"PRAGMA foreign_key_list({identifier})").fetchall())
            foreign_by_column: dict[str, dict[str, Any]] = {}
            for foreign_key in foreign_keys:
                foreign_by_column[foreign_key["from"]] = {
                    "table": foreign_key["table"],
                    "from": foreign_key["from"],
                    "to": foreign_key["to"],
                    "on_update": foreign_key["on_update"],
                    "on_delete": foreign_key["on_delete"],
                    "group_id": foreign_key["id"],
                    "sequence": foreign_key["seq"],
                }
            columns = []
            for row in raw_columns:
                column = dict(row)
                column["nullable"] = not bool(row["notnull"]) and not bool(row["pk"])
                column["generated"] = bool(single_integer_pk and row["name"] == primary_key[0])
                column["enum_options"] = self._parse_enum_options(create_sql, row["name"])
                json_pattern = re.compile(rf"json_valid\s*\(\s*{re.escape(row['name'])}\s*\)", re.IGNORECASE)
                column["json"] = bool(json_pattern.search(create_sql))
                column["foreign_key"] = foreign_by_column.get(row["name"])
                columns.append(column)
            inbound: list[dict[str, Any]] = []
            table_rows = connection.execute(
                "SELECT name FROM sqlite_schema WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            ).fetchall()
            for child_row in table_rows:
                child = child_row["name"]
                child_identifier = self._quoted_identifier(child, {child})
                for foreign_key in connection.execute(f"PRAGMA foreign_key_list({child_identifier})").fetchall():
                    if foreign_key["table"] == name:
                        inbound.append(
                            {
                                "table": child,
                                "from": foreign_key["from"],
                                "to": foreign_key["to"],
                                "on_update": foreign_key["on_update"],
                                "on_delete": foreign_key["on_delete"],
                                "group_id": foreign_key["id"],
                                "sequence": foreign_key["seq"],
                            }
                        )
            return {
                "name": name,
                "kind": schema_row["type"],
                "editable": self.editable and schema_row["type"] == "table",
                "columns": columns,
                "primary_key": primary_key,
                "foreign_keys": foreign_keys,
                "inbound_foreign_keys": inbound,
            }
        finally:
            if owns_connection:
                connection.close()

    @staticmethod
    def _row_etag(row: dict[str, Any]) -> str:
        payload = json.dumps(_json_safe(row), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _row_key(schema: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
        return {column: row.get(column) for column in schema["primary_key"]}

    def editor_table_data(self, name: str, limit: int = 50, offset: int = 0, query: str = "") -> dict[str, Any]:
        self._ensure_editable()
        schema = self.table_schema(name, require_table=True)
        page = self.table_data(name, limit, offset, query)
        return {
            **page,
            "schema": schema,
            "rows": [
                {
                    "values": row,
                    "key": self._row_key(schema, row),
                    "etag": self._row_etag(row),
                }
                for row in page["rows"]
            ],
        }

    def foreign_key_options(self, table: str, value_column: str, query: str = "") -> list[dict[str, Any]]:
        self._ensure_editable()
        schema = self.table_schema(table, require_table=True)
        columns = {column["name"] for column in schema["columns"]}
        if value_column not in columns:
            raise EditorError(HTTPStatus.BAD_REQUEST, "unknown_column", "Поле внешнего ключа не найдено")
        preferred_labels = [
            column for column in ("code", "public_id", "pseudonym", "name", "title", "citation_apa", "version_name")
            if column in columns and column != value_column
        ]
        label_columns = preferred_labels[:2] or [value_column]
        identifier = self._quoted_identifier(table, {table})
        value_identifier = self._quoted_identifier(value_column, columns)
        label_sql = " || ' · ' || ".join(
            f"COALESCE(CAST({self._quoted_identifier(column, columns)} AS TEXT), '')"
            for column in label_columns
        )
        parameters: list[Any] = []
        where = ""
        if query:
            query_clauses = [
                f"CAST({self._quoted_identifier(column, columns)} AS TEXT) LIKE ?"
                for column in [value_column, *label_columns]
            ]
            where = " WHERE " + " OR ".join(query_clauses)
            parameters.extend([f"%{query[:100]}%"] * len(query_clauses))
        with self.session() as connection:
            rows = connection.execute(
                f"SELECT {value_identifier} AS value, {label_sql} AS label FROM {identifier}{where} ORDER BY label LIMIT 100",
                parameters,
            ).fetchall()
        return [{"value": row["value"], "label": row["label"] or str(row["value"])} for row in rows]

    def _ensure_editable(self) -> None:
        if not self.editable:
            raise EditorError(HTTPStatus.METHOD_NOT_ALLOWED, "read_only", "Режим редактирования не включён")

    @staticmethod
    def _column_map(schema: dict[str, Any]) -> dict[str, dict[str, Any]]:
        return {column["name"]: column for column in schema["columns"]}

    def _coerce_values(
        self,
        schema: dict[str, Any],
        values: dict[str, Any],
        *,
        update: bool,
    ) -> dict[str, Any]:
        if not isinstance(values, dict):
            raise EditorError(HTTPStatus.BAD_REQUEST, "invalid_values", "Поле values должно быть объектом")
        columns = self._column_map(schema)
        result: dict[str, Any] = {}
        for name, value in values.items():
            if name not in columns:
                raise EditorError(HTTPStatus.BAD_REQUEST, "unknown_column", f"Неизвестная колонка: {name}")
            column = columns[name]
            if update and name in schema["primary_key"]:
                raise EditorError(HTTPStatus.BAD_REQUEST, "primary_key_is_immutable", "Первичный ключ нельзя менять")
            if column["generated"] and value in (None, "") and not update:
                continue
            if value is None:
                result[name] = None
                continue
            declared_type = (column["type"] or "TEXT").upper()
            try:
                if "INT" in declared_type:
                    value = int(value)
                elif any(token in declared_type for token in ("REAL", "FLOA", "DOUB", "NUM")):
                    value = float(value)
                elif "BLOB" in declared_type:
                    raise ValueError("BLOB-поля не поддерживаются редактором")
                elif not isinstance(value, str):
                    value = json.dumps(value, ensure_ascii=False) if column["json"] else str(value)
            except (TypeError, ValueError) as error:
                raise EditorError(
                    HTTPStatus.UNPROCESSABLE_ENTITY,
                    "invalid_field_value",
                    f"Некорректное значение поля {name}: {error}",
                    field=name,
                ) from error
            if column["json"] and value != "":
                try:
                    json.loads(value)
                except (TypeError, json.JSONDecodeError) as error:
                    raise EditorError(
                        HTTPStatus.UNPROCESSABLE_ENTITY,
                        "invalid_json",
                        f"Поле {name} должно содержать корректный JSON",
                        field=name,
                    ) from error
            result[name] = value
        if not result and update:
            raise EditorError(HTTPStatus.BAD_REQUEST, "no_changes", "Нет полей для изменения")
        return result

    def _get_row(
        self,
        connection: sqlite3.Connection,
        table: str,
        schema: dict[str, Any],
        key: dict[str, Any],
    ) -> dict[str, Any] | None:
        if not isinstance(key, dict) or set(key) != set(schema["primary_key"]):
            raise EditorError(HTTPStatus.BAD_REQUEST, "invalid_key", "Передан неполный первичный ключ")
        columns = {column["name"] for column in schema["columns"]}
        identifier = self._quoted_identifier(table, {table})
        clauses = [f"{self._quoted_identifier(column, columns)} IS ?" for column in schema["primary_key"]]
        row = connection.execute(
            f"SELECT * FROM {identifier} WHERE {' AND '.join(clauses)}",
            [key[column] for column in schema["primary_key"]],
        ).fetchone()
        return dict(row) if row else None

    def _ensure_backup_before_commit(self) -> Path:
        if self.backup_path is not None:
            return self.backup_path
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        target = self.backup_dir / f"{self.path.stem}_{timestamp}_{self.startup_sha256[:8]}.sqlite"
        suffix = 1
        while target.exists():
            target = self.backup_dir / f"{self.path.stem}_{timestamp}_{self.startup_sha256[:8]}_{suffix}.sqlite"
            suffix += 1
        source = self.connect(force_read_only=True)
        destination = sqlite3.connect(target)
        try:
            source.backup(destination)
        finally:
            destination.close()
            source.close()
        os.chmod(target, 0o600)
        self.backup_path = target
        return target

    def _append_journal(self, entry: dict[str, Any]) -> str | None:
        try:
            self.journal_path.parent.mkdir(parents=True, exist_ok=True)
            with self.journal_path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(_json_safe(entry), ensure_ascii=False, separators=(",", ":")) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.chmod(self.journal_path, 0o600)
            except OSError:
                pass
            return None
        except OSError as error:
            return str(error)

    @staticmethod
    def _check_foreign_keys(connection: sqlite3.Connection) -> None:
        violations = connection.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise EditorError(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "foreign_key_check_failed",
                "Изменение нарушает внешние ключи",
            )

    def _result_row(self, schema: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
        return {"values": row, "key": self._row_key(schema, row), "etag": self._row_etag(row)}

    def insert_row(self, table: str, values: dict[str, Any]) -> dict[str, Any]:
        self._ensure_editable()
        with self._write_lock, self.session() as connection:
            schema = self.table_schema(table, require_table=True, connection=connection)
            clean = self._coerce_values(schema, values, update=False)
            columns = self._column_map(schema)
            identifier = self._quoted_identifier(table, {table})
            try:
                connection.execute("BEGIN IMMEDIATE")
                if clean:
                    names = list(clean)
                    column_sql = ", ".join(self._quoted_identifier(name, set(columns)) for name in names)
                    placeholders = ", ".join("?" for _ in names)
                    cursor = connection.execute(
                        f"INSERT INTO {identifier} ({column_sql}) VALUES ({placeholders})",
                        [clean[name] for name in names],
                    )
                else:
                    cursor = connection.execute(f"INSERT INTO {identifier} DEFAULT VALUES")
                key: dict[str, Any]
                if len(schema["primary_key"]) == 1 and self._column_map(schema)[schema["primary_key"][0]]["generated"]:
                    key = {schema["primary_key"][0]: cursor.lastrowid}
                else:
                    key = {column: clean.get(column) for column in schema["primary_key"]}
                row = self._get_row(connection, table, schema, key)
                if row is None:
                    raise EditorError(HTTPStatus.INTERNAL_SERVER_ERROR, "insert_lookup_failed", "Добавленная строка не найдена")
                self._check_foreign_keys(connection)
                backup = self._ensure_backup_before_commit()
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        warning = self._append_journal(
            {
                "timestamp": _utc_now(),
                "action": "insert",
                "table": table,
                "key": key,
                "before": None,
                "after": row,
                "backup": backup.name,
            }
        )
        return {"row": self._result_row(schema, row), "journal_warning": warning}

    def update_row(self, table: str, key: dict[str, Any], values: dict[str, Any], etag: str) -> dict[str, Any]:
        self._ensure_editable()
        with self._write_lock, self.session() as connection:
            schema = self.table_schema(table, require_table=True, connection=connection)
            clean = self._coerce_values(schema, values, update=True)
            columns = self._column_map(schema)
            identifier = self._quoted_identifier(table, {table})
            try:
                connection.execute("BEGIN IMMEDIATE")
                before = self._get_row(connection, table, schema, key)
                if before is None:
                    raise EditorError(HTTPStatus.NOT_FOUND, "row_not_found", "Строка не найдена")
                if self._row_etag(before) != etag:
                    raise EditorError(HTTPStatus.CONFLICT, "stale_row", "Строка была изменена; обновите таблицу")
                changed = {name: value for name, value in clean.items() if before.get(name) != value}
                if not changed:
                    connection.rollback()
                    return {"row": self._result_row(schema, before), "unchanged": True, "journal_warning": None}
                set_sql = ", ".join(
                    f"{self._quoted_identifier(name, set(columns))}=?" for name in changed
                )
                key_sql = " AND ".join(
                    f"{self._quoted_identifier(name, set(columns))} IS ?" for name in schema["primary_key"]
                )
                connection.execute(
                    f"UPDATE {identifier} SET {set_sql} WHERE {key_sql}",
                    [*changed.values(), *[key[name] for name in schema["primary_key"]]],
                )
                after = self._get_row(connection, table, schema, key)
                if after is None:
                    raise EditorError(HTTPStatus.INTERNAL_SERVER_ERROR, "update_lookup_failed", "Изменённая строка не найдена")
                self._check_foreign_keys(connection)
                backup = self._ensure_backup_before_commit()
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        warning = self._append_journal(
            {
                "timestamp": _utc_now(),
                "action": "update",
                "table": table,
                "key": key,
                "before": before,
                "after": after,
                "backup": backup.name,
            }
        )
        return {"row": self._result_row(schema, after), "journal_warning": warning}

    def _delete_preview_with_connection(
        self,
        connection: sqlite3.Connection,
        table: str,
        key: dict[str, Any],
        etag: str,
    ) -> dict[str, Any]:
        schema = self.table_schema(table, require_table=True, connection=connection)
        row = self._get_row(connection, table, schema, key)
        if row is None:
            raise EditorError(HTTPStatus.NOT_FOUND, "row_not_found", "Строка не найдена")
        if self._row_etag(row) != etag:
            raise EditorError(HTTPStatus.CONFLICT, "stale_row", "Строка была изменена; обновите таблицу")
        references: list[dict[str, Any]] = []
        for foreign_key in schema["inbound_foreign_keys"]:
            parent_column = foreign_key["to"] or schema["primary_key"][0]
            child = foreign_key["table"]
            child_schema = self.table_schema(child, require_table=True, connection=connection)
            child_columns = {column["name"] for column in child_schema["columns"]}
            child_identifier = self._quoted_identifier(child, {child})
            from_identifier = self._quoted_identifier(foreign_key["from"], child_columns)
            count = connection.execute(
                f"SELECT COUNT(*) FROM {child_identifier} WHERE {from_identifier} IS ?",
                (row[parent_column],),
            ).fetchone()[0]
            if count:
                references.append({**foreign_key, "count": count})
        token_payload = json.dumps(
            {"table": table, "key": key, "etag": etag, "references": references},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        confirmation_token = hashlib.sha256(
            f"{self.editor_token}:{token_payload}".encode("utf-8")
        ).hexdigest()
        return {
            "table": table,
            "key": key,
            "etag": etag,
            "row": row,
            "references": references,
            "dependent_rows": sum(item["count"] for item in references),
            "requires_typed_confirmation": bool(references),
            "confirmation_token": confirmation_token,
        }

    def delete_preview(self, table: str, key: dict[str, Any], etag: str) -> dict[str, Any]:
        self._ensure_editable()
        with self.session() as connection:
            return self._delete_preview_with_connection(connection, table, key, etag)

    def delete_row(
        self,
        table: str,
        key: dict[str, Any],
        etag: str,
        confirmation_token: str,
        confirmation_text: str = "",
    ) -> dict[str, Any]:
        self._ensure_editable()
        with self._write_lock, self.session() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                preview = self._delete_preview_with_connection(connection, table, key, etag)
                if not secrets.compare_digest(preview["confirmation_token"], confirmation_token or ""):
                    raise EditorError(HTTPStatus.CONFLICT, "invalid_confirmation", "Подтверждение удаления устарело")
                if preview["requires_typed_confirmation"] and confirmation_text != table:
                    raise EditorError(
                        HTTPStatus.BAD_REQUEST,
                        "typed_confirmation_required",
                        f"Для удаления связанных строк введите название таблицы: {table}",
                    )
                schema = self.table_schema(table, require_table=True, connection=connection)
                columns = self._column_map(schema)
                identifier = self._quoted_identifier(table, {table})
                key_sql = " AND ".join(
                    f"{self._quoted_identifier(name, set(columns))} IS ?" for name in schema["primary_key"]
                )
                connection.execute(
                    f"DELETE FROM {identifier} WHERE {key_sql}",
                    [key[name] for name in schema["primary_key"]],
                )
                self._check_foreign_keys(connection)
                backup = self._ensure_backup_before_commit()
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        warning = self._append_journal(
            {
                "timestamp": _utc_now(),
                "action": "delete",
                "table": table,
                "key": key,
                "before": preview["row"],
                "after": None,
                "dependent_rows": preview["dependent_rows"],
                "backup": backup.name,
            }
        )
        return {"deleted": True, "key": key, "journal_warning": warning}

    def history(self, limit: int = 50) -> list[dict[str, Any]]:
        self._ensure_editable()
        limit = max(1, min(int(limit), 200))
        if not self.journal_path.is_file():
            return []
        lines = self.journal_path.read_text(encoding="utf-8").splitlines()
        entries = []
        for line in reversed(lines[-limit:]):
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return entries

    def editor_status(self, include_token: bool = False) -> dict[str, Any]:
        current_sha256 = self.file_sha256()
        static_sha256 = None
        if STATIC_BUILD_INFO.is_file():
            try:
                static_sha256 = json.loads(STATIC_BUILD_INFO.read_text(encoding="utf-8")).get("source_sha256")
            except (OSError, json.JSONDecodeError):
                static_sha256 = None
        return {
            "enabled": self.editable,
            "database_file": self.path.name,
            "current_sha256": current_sha256,
            "startup_sha256": self.startup_sha256,
            "changes_since_start": current_sha256 != self.startup_sha256,
            "backup_created": self.backup_path is not None,
            "backup_file": self.backup_path.name if self.backup_path else None,
            "unpublished_changes": static_sha256 is not None and static_sha256 != current_sha256,
            "static_snapshot_known": static_sha256 is not None,
            "csrf_token": self.editor_token if include_token and self.editable else None,
        }


class ViewerHandler(BaseHTTPRequestHandler):
    database: Database
    static_dir: Path
    erd_path: Path
    mmd_path: Path

    server_version = "TyumGUDBViewer/1.1"

    def log_message(self, format_string: str, *args: Any) -> None:
        sys.stderr.write("[db-viewer] " + format_string % args + "\n")

    def _security_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'self'",
        )

    def _send_json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self._security_headers()
        self.end_headers()
        self.wfile.write(body)

    def _send_editor_error(self, error: EditorError) -> None:
        self._send_json(
            {"error": error.code, "detail": error.detail, **error.extra},
            error.status,
        )

    def _read_json(self) -> dict[str, Any]:
        raw_length = self.headers.get("Content-Length", "")
        try:
            length = int(raw_length)
        except ValueError as error:
            raise EditorError(HTTPStatus.BAD_REQUEST, "invalid_content_length", "Некорректный Content-Length") from error
        if length <= 0 or length > MAX_JSON_BODY:
            raise EditorError(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE if length > MAX_JSON_BODY else HTTPStatus.BAD_REQUEST,
                "invalid_body_size",
                "Тело запроса отсутствует или превышает 1 МБ",
            )
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise EditorError(HTTPStatus.BAD_REQUEST, "invalid_json", "Ожидается корректный JSON") from error
        if not isinstance(payload, dict):
            raise EditorError(HTTPStatus.BAD_REQUEST, "invalid_json_shape", "Корнем JSON должен быть объект")
        return payload

    def _validate_editor_request(self) -> None:
        if not self.database.editable:
            raise EditorError(HTTPStatus.METHOD_NOT_ALLOWED, "read_only", "Режим редактирования не включён")
        host = self.headers.get("Host", "")
        allowed_hosts = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
        if host not in allowed_hosts:
            raise EditorError(HTTPStatus.FORBIDDEN, "invalid_host", "Запрос разрешён только с локального адреса")
        origin = self.headers.get("Origin", "")
        if origin != f"http://{host}":
            raise EditorError(HTTPStatus.FORBIDDEN, "invalid_origin", "Запись разрешена только из локального интерфейса")
        token = self.headers.get("X-CSRF-Token", "")
        if not secrets.compare_digest(token, self.database.editor_token):
            raise EditorError(HTTPStatus.FORBIDDEN, "invalid_csrf_token", "Сессионный токен редактирования недействителен")

    def _send_file(self, path: Path, cache: bool = True) -> None:
        if not path.is_file():
            self._send_json({"error": "not_found"}, HTTPStatus.NOT_FOUND)
            return
        body = path.read_bytes()
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if path.suffix == ".mmd":
            content_type = "text/plain"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8" if content_type.startswith("text/") else content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "public, max-age=300" if cache else "no-store")
        self._security_headers()
        self.end_headers()
        self.wfile.write(body)

    def _api_route(self, path: str, query: dict[str, list[str]]) -> bool:
        if path == "/health":
            summary = self.database.summary()
            self._send_json(
                {
                    "status": "ok" if summary["database"]["quick_check"] == "ok" else "degraded",
                    "database": summary["database"],
                }
            )
            return True
        if path == "/api/summary":
            self._send_json(self.database.summary())
            return True
        if path == "/api/editor/status":
            self._send_json(self.database.editor_status(include_token=True))
            return True
        if path == "/api/editor/history":
            try:
                limit = int(query.get("limit", ["50"])[0])
                self._send_json({"items": self.database.history(limit)})
            except ValueError:
                self._send_json({"error": "invalid_limit"}, HTTPStatus.BAD_REQUEST)
            return True
        if path.startswith("/api/editor/options/"):
            table = unquote(path.rsplit("/", 1)[-1])
            value_column = query.get("column", [""])[0]
            options = self.database.foreign_key_options(table, value_column, query.get("q", [""])[0])
            self._send_json({"items": options})
            return True
        if path.startswith("/api/editor/tables/"):
            parts = path.strip("/").split("/")
            if len(parts) == 4:
                table = unquote(parts[3])
                try:
                    limit = int(query.get("limit", ["50"])[0])
                    offset = int(query.get("offset", ["0"])[0])
                    table_query = query.get("q", [""])[0]
                    self._send_json(self.database.editor_table_data(table, limit, offset, table_query))
                except (KeyError, ValueError):
                    self._send_json({"error": "unknown_table_or_invalid_pagination"}, HTTPStatus.NOT_FOUND)
                return True
        if path == "/api/search":
            self._send_json(self.database.search(query.get("q", [""])[0]))
            return True
        if path == "/api/criteria":
            filters = {key: values[0] for key, values in query.items() if values}
            self._send_json({"items": self.database.criteria(filters)})
            return True
        if path.startswith("/api/criteria/"):
            code = unquote(path.rsplit("/", 1)[-1])
            item = self.database.criterion(code)
            self._send_json(item if item else {"error": "not_found"}, HTTPStatus.OK if item else HTTPStatus.NOT_FOUND)
            return True
        if path == "/api/sources":
            self._send_json({"items": self.database.research_sources(query.get("q", [""])[0])})
            return True
        if path.startswith("/api/sources/"):
            code = unquote(path.rsplit("/", 1)[-1])
            item = self.database.research_source(code)
            self._send_json(item if item else {"error": "not_found"}, HTTPStatus.OK if item else HTTPStatus.NOT_FOUND)
            return True
        if path == "/api/instruments":
            self._send_json({"items": self.database.instruments()})
            return True
        if path.startswith("/api/instruments/"):
            code = unquote(path.rsplit("/", 1)[-1])
            item = self.database.instrument(code)
            self._send_json(item if item else {"error": "not_found"}, HTTPStatus.OK if item else HTTPStatus.NOT_FOUND)
            return True
        if path == "/api/conditions":
            self._send_json({"items": self.database.conditions()})
            return True
        if path.startswith("/api/conditions/"):
            code = unquote(path.rsplit("/", 1)[-1])
            item = self.database.condition(code)
            self._send_json(item if item else {"error": "not_found"}, HTTPStatus.OK if item else HTTPStatus.NOT_FOUND)
            return True
        if path == "/api/effects":
            self._send_json({"items": self.database.effects()})
            return True
        if path.startswith("/api/effects/"):
            code = unquote(path.rsplit("/", 1)[-1])
            item = self.database.effect(code)
            self._send_json(item if item else {"error": "not_found"}, HTTPStatus.OK if item else HTTPStatus.NOT_FOUND)
            return True
        if path == "/api/tables":
            self._send_json({"items": self.database.tables()})
            return True
        if path.startswith("/api/tables/"):
            name = unquote(path.rsplit("/", 1)[-1])
            try:
                limit = int(query.get("limit", ["50"])[0])
                offset = int(query.get("offset", ["0"])[0])
                table_query = query.get("q", [""])[0]
                self._send_json(self.database.table_data(name, limit, offset, table_query))
            except (KeyError, ValueError):
                self._send_json({"error": "unknown_table_or_invalid_pagination"}, HTTPStatus.NOT_FOUND)
            return True
        return False

    def _editor_mutation_route(self, method: str, path: str, payload: dict[str, Any]) -> bool:
        parts = path.strip("/").split("/")
        if len(parts) != 5 or parts[:3] != ["api", "editor", "tables"]:
            return False
        table = unquote(parts[3])
        operation = parts[4]
        if method == "POST" and operation == "rows":
            self._send_json(
                self.database.insert_row(table, payload.get("values")),
                HTTPStatus.CREATED,
            )
            return True
        if method == "PATCH" and operation == "rows":
            self._send_json(
                self.database.update_row(
                    table,
                    payload.get("key"),
                    payload.get("values"),
                    str(payload.get("etag") or ""),
                )
            )
            return True
        if method == "POST" and operation == "delete-preview":
            self._send_json(
                self.database.delete_preview(
                    table,
                    payload.get("key"),
                    str(payload.get("etag") or ""),
                )
            )
            return True
        if method == "DELETE" and operation == "rows":
            self._send_json(
                self.database.delete_row(
                    table,
                    payload.get("key"),
                    str(payload.get("etag") or ""),
                    str(payload.get("confirmation_token") or ""),
                    str(payload.get("confirmation_text") or ""),
                )
            )
            return True
        return False

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        try:
            if self._api_route(path, query):
                return
            if path == "/assets/erd.svg":
                self._send_file(self.erd_path)
                return
            if path == "/assets/erd.mmd":
                self._send_file(self.mmd_path, cache=False)
                return
            if path == "/":
                self._send_file(self.static_dir / "index.html", cache=False)
                return
            if path.startswith("/static/"):
                relative = Path(unquote(path.removeprefix("/static/")))
                candidate = (self.static_dir / relative).resolve()
                if self.static_dir.resolve() not in candidate.parents:
                    self._send_json({"error": "not_found"}, HTTPStatus.NOT_FOUND)
                    return
                self._send_file(candidate, cache=not self.database.editable)
                return
            self._send_json({"error": "not_found"}, HTTPStatus.NOT_FOUND)
        except EditorError as error:
            self._send_editor_error(error)
        except (sqlite3.Error, OSError) as error:
            self._send_json({"error": "database_or_file_error", "detail": str(error)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def _handle_mutation(self, method: str) -> None:
        parsed = urlparse(self.path)
        try:
            self._validate_editor_request()
            payload = self._read_json()
            if not self._editor_mutation_route(method, parsed.path, payload):
                self._send_json({"error": "not_found"}, HTTPStatus.NOT_FOUND)
        except EditorError as error:
            self._send_editor_error(error)
        except sqlite3.IntegrityError as error:
            self._send_json(
                {"error": "constraint_violation", "detail": str(error)},
                HTTPStatus.UNPROCESSABLE_ENTITY,
            )
        except sqlite3.OperationalError as error:
            status = HTTPStatus.CONFLICT if "locked" in str(error).lower() else HTTPStatus.UNPROCESSABLE_ENTITY
            self._send_json({"error": "database_write_error", "detail": str(error)}, status)
        except (sqlite3.Error, OSError) as error:
            self._send_json({"error": "database_or_file_error", "detail": str(error)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_POST(self) -> None:  # noqa: N802
        self._handle_mutation("POST")

    def do_PATCH(self) -> None:  # noqa: N802
        self._handle_mutation("PATCH")

    def do_DELETE(self) -> None:  # noqa: N802
        self._handle_mutation("DELETE")

    def do_PUT(self) -> None:  # noqa: N802
        self._send_json({"error": "method_not_allowed"}, HTTPStatus.METHOD_NOT_ALLOWED)


def make_handler(database: Database, static_dir: Path = STATIC_DIR) -> type[ViewerHandler]:
    class ConfiguredHandler(ViewerHandler):
        pass

    ConfiguredHandler.database = database
    ConfiguredHandler.static_dir = static_dir
    ConfiguredHandler.erd_path = DEFAULT_ERD
    ConfiguredHandler.mmd_path = DEFAULT_MMD
    return ConfiguredHandler


def create_server(
    database_path: Path,
    port: int = 8000,
    *,
    edit: bool = False,
    backup_dir: Path = DEFAULT_BACKUP_DIR,
    journal_path: Path = DEFAULT_JOURNAL,
) -> ThreadingHTTPServer:
    database = Database(database_path, editable=edit, backup_dir=backup_dir, journal_path=journal_path)
    handler = make_handler(database)
    return ThreadingHTTPServer(("127.0.0.1", port), handler)


def main() -> None:
    parser = argparse.ArgumentParser(description="Local viewer for the TyumGU pilot SQLite database")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="Path to the SQLite database")
    parser.add_argument("--port", type=int, default=8000, help="Loopback port (default: 8000)")
    parser.add_argument("--open", action="store_true", help="Open the local page in the default browser")
    parser.add_argument("--edit", action="store_true", help="Enable local form-based database editing")
    args = parser.parse_args()
    if not (1 <= args.port <= 65535):
        parser.error("--port must be between 1 and 65535")
    try:
        server = create_server(args.db, args.port, edit=args.edit)
    except FileNotFoundError as error:
        parser.error(str(error))
    url = f"http://127.0.0.1:{server.server_port}"
    print(f"TyumGU DB Viewer: {url}")
    print(f"Database: {args.db.resolve()} ({'editable' if args.edit else 'read-only'})")
    if args.edit:
        print(f"Backups: {DEFAULT_BACKUP_DIR}")
        print("Public static snapshot is not rebuilt automatically.")
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
