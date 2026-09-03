#!/usr/bin/env python3
"""Export the current SQLite working database as a reproducible SQL snapshot."""

from __future__ import annotations

import argparse
import hashlib
import os
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from server import DEFAULT_DB, VAR_DIR


DEFAULT_EXPORT_DIR = VAR_DIR / "exports"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def export_database(database_path: Path, output_path: Path | None = None) -> Path:
    database_path = database_path.resolve()
    if not database_path.is_file():
        raise FileNotFoundError(f"SQLite database not found: {database_path}")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if output_path is None:
        output_path = DEFAULT_EXPORT_DIR / f"{database_path.stem}_{timestamp}.sql"
    output_path = output_path.resolve()
    if output_path.exists():
        raise FileExistsError(f"Refusing to overwrite existing export: {output_path}")
    if output_path == database_path:
        raise ValueError("Export path must differ from the SQLite database")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    uri_path = quote(database_path.as_posix(), safe="/:")
    connection = sqlite3.connect(f"file:{uri_path}?mode=ro", uri=True, timeout=5)
    try:
        connection.execute("PRAGMA query_only = ON")
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"SQLite integrity_check failed: {integrity}")
        source_sha256 = sha256(database_path)
        header = (
            "-- Current TyumGU pilot database snapshot\n"
            f"-- Exported at: {datetime.now(timezone.utc).isoformat(timespec='seconds')}\n"
            f"-- Source: {database_path.name}\n"
            f"-- Source SHA-256: {source_sha256}\n"
            "PRAGMA foreign_keys = OFF;\n"
        )
        fd, temporary_name = tempfile.mkstemp(
            prefix=f".{output_path.name}.",
            suffix=".tmp",
            dir=output_path.parent,
            text=True,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(header)
                for statement in connection.iterdump():
                    stream.write(statement)
                    stream.write("\n")
                stream.write("PRAGMA foreign_keys = ON;\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_name, output_path)
        finally:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)
    finally:
        connection.close()
    os.chmod(output_path, 0o600)
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Export the current TyumGU pilot SQLite database to SQL")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="Source SQLite database")
    parser.add_argument("--output", type=Path, help="Target SQL file; defaults to db-viewer/var/exports")
    args = parser.parse_args()
    try:
        output = export_database(args.db, args.output)
    except (FileNotFoundError, FileExistsError, RuntimeError, ValueError) as error:
        parser.error(str(error))
    print(f"SQL snapshot: {output}")
    print(f"SHA-256: {sha256(output)}")


if __name__ == "__main__":
    main()
