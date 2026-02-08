"""Version-controlled schema migrations for the AI News Platform."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Callable, Dict, List, Tuple

logger = logging.getLogger(__name__)

# Each migration is (version, description, list_of_sql_statements)
MigrationStep = Tuple[int, str, List[str]]

SCHEMA_SQL_PATH = Path(__file__).parent / "schema.sql"


def _get_migrations() -> List[MigrationStep]:
    """Return ordered list of migrations."""
    return [
        (
            1,
            "Initial schema: sources, items, metrics, digests, FTS5, indexes",
            [SCHEMA_SQL_PATH.read_text(encoding="utf-8")],
        ),
        (
            2,
            "Add items.fetch_batch_id for tracking ingest runs",
            [
                "ALTER TABLE items ADD COLUMN fetch_batch_id TEXT;",
                "CREATE INDEX IF NOT EXISTS idx_items_batch ON items(fetch_batch_id);",
            ],
        ),
    ]


def get_current_version(conn: sqlite3.Connection) -> int:
    """Get the current schema version, or 0 if no schema exists."""
    try:
        row = conn.execute(
            "SELECT MAX(version) FROM schema_version"
        ).fetchone()
        return row[0] if row and row[0] is not None else 0
    except sqlite3.OperationalError:
        return 0


def apply_migrations(db_path: str) -> int:
    """Apply all pending migrations. Returns the final schema version."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    current = get_current_version(conn)
    migrations = _get_migrations()
    applied = 0

    for version, description, statements in migrations:
        if version <= current:
            continue

        logger.info("Applying migration v%d: %s", version, description)
        try:
            for sql in statements:
                conn.executescript(sql)
            conn.execute(
                "INSERT INTO schema_version (version, description) VALUES (?, ?)",
                (version, description),
            )
            conn.commit()
            applied += 1
            logger.info("Migration v%d applied successfully", version)
        except Exception:
            conn.rollback()
            logger.exception("Migration v%d failed", version)
            raise

    final = get_current_version(conn)
    conn.close()

    if applied:
        logger.info("Applied %d migration(s). Schema at v%d", applied, final)
    else:
        logger.info("Schema up to date at v%d", final)

    return final


def reset_database(db_path: str) -> None:
    """Drop all tables and re-apply migrations from scratch. USE WITH CAUTION."""
    conn = sqlite3.connect(db_path)

    # Get all tables
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()

    for (name,) in tables:
        if name == "items_fts" or name.startswith("items_fts_"):
            continue  # FTS virtual tables need special handling
        conn.execute(f"DROP TABLE IF EXISTS [{name}]")

    # Drop FTS table
    try:
        conn.execute("DROP TABLE IF EXISTS items_fts")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()

    apply_migrations(db_path)
