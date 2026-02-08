"""High-performance SQLite database manager with FTS5 and WAL mode."""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import time
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional, Sequence, Tuple

import aiosqlite

from backend.storage.models import Digest, Item, Metric, Source
from backend.storage.migrations import apply_migrations

logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 1000
DEFAULT_SEARCH_LIMIT = 50


class DatabaseManager:
    """Async SQLite manager with connection pooling, FTS5, and WAL mode.

    Usage:
        db = DatabaseManager("data/ainews.db")
        await db.initialize()
        # ... use db ...
        await db.close()
    """

    def __init__(
        self,
        db_path: str,
        batch_size: int = DEFAULT_BATCH_SIZE,
        cache_size_mb: int = 64,
    ):
        self.db_path = db_path
        self.batch_size = batch_size
        self.cache_size_mb = cache_size_mb
        self._conn: Optional[aiosqlite.Connection] = None
        self._write_lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Create database, apply migrations, and configure pragmas."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        # Apply migrations synchronously (schema changes)
        apply_migrations(self.db_path)

        # Open async connection
        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row

        # Performance pragmas
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute(f"PRAGMA cache_size=-{self.cache_size_mb * 1000}")
        await self._conn.execute("PRAGMA synchronous=NORMAL")
        await self._conn.execute("PRAGMA temp_store=MEMORY")
        await self._conn.execute("PRAGMA foreign_keys=ON")
        await self._conn.execute("PRAGMA mmap_size=268435456")  # 256MB mmap

        logger.info("Database initialized: %s", self.db_path)

    async def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            await self._conn.close()
            self._conn = None

    @asynccontextmanager
    async def _transaction(self) -> AsyncIterator[aiosqlite.Connection]:
        """Acquire write lock and begin a transaction."""
        assert self._conn is not None, "Database not initialized"
        async with self._write_lock:
            await self._conn.execute("BEGIN IMMEDIATE")
            try:
                yield self._conn
                await self._conn.commit()
            except Exception:
                await self._conn.rollback()
                raise

    # --- Sources ---

    async def upsert_source(self, source: Source) -> None:
        """Insert or update a source."""
        assert self._conn is not None
        async with self._write_lock:
            await self._conn.execute(
                """INSERT INTO sources (id, config, last_fetch_at, last_error, error_count, enabled)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                       config=excluded.config,
                       last_fetch_at=excluded.last_fetch_at,
                       last_error=excluded.last_error,
                       error_count=excluded.error_count,
                       enabled=excluded.enabled""",
                source.to_row(),
            )
            await self._conn.commit()

    async def get_source(self, source_id: str) -> Optional[Source]:
        """Get a source by ID."""
        assert self._conn is not None
        cursor = await self._conn.execute(
            "SELECT * FROM sources WHERE id = ?", (source_id,)
        )
        row = await cursor.fetchone()
        return Source.from_row(dict(row)) if row else None

    async def get_enabled_sources(self) -> List[Source]:
        """Get all enabled sources."""
        assert self._conn is not None
        cursor = await self._conn.execute(
            "SELECT * FROM sources WHERE enabled = 1"
        )
        rows = await cursor.fetchall()
        return [Source.from_row(dict(r)) for r in rows]

    async def update_source_status(
        self,
        source_id: str,
        last_fetch_at: Optional[datetime] = None,
        last_error: Optional[str] = None,
        increment_errors: bool = False,
    ) -> None:
        """Update source fetch status."""
        assert self._conn is not None
        async with self._write_lock:
            if last_error:
                if increment_errors:
                    await self._conn.execute(
                        """UPDATE sources
                           SET last_error = ?, error_count = error_count + 1,
                               last_fetch_at = COALESCE(?, last_fetch_at)
                           WHERE id = ?""",
                        (last_error, last_fetch_at and last_fetch_at.isoformat(), source_id),
                    )
                else:
                    await self._conn.execute(
                        """UPDATE sources SET last_error = ?, last_fetch_at = ?
                           WHERE id = ?""",
                        (last_error, last_fetch_at and last_fetch_at.isoformat(), source_id),
                    )
            else:
                await self._conn.execute(
                    """UPDATE sources
                       SET last_fetch_at = ?, last_error = NULL, error_count = 0
                       WHERE id = ?""",
                    (last_fetch_at and last_fetch_at.isoformat(), source_id),
                )
            await self._conn.commit()

    # --- Items ---

    async def batch_insert_items(self, items: List[Item]) -> int:
        """Insert items in batches, skipping duplicates. Returns count inserted."""
        if not items:
            return 0

        inserted = 0
        async with self._transaction() as conn:
            for i in range(0, len(items), self.batch_size):
                batch = items[i : i + self.batch_size]
                rows = [item.to_row() for item in batch]
                cursor = await conn.executemany(
                    """INSERT OR IGNORE INTO items
                       (id, source_id, external_id, url, url_canonical, title, content,
                        author, published_at, ingested_at, category, language, metadata,
                        snapshot_path)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    rows,
                )
                inserted += cursor.rowcount

        logger.info("Batch insert: %d/%d items inserted", inserted, len(items))
        return inserted

    async def get_item(self, item_id: str) -> Optional[Item]:
        """Get an item by ID."""
        assert self._conn is not None
        cursor = await self._conn.execute(
            "SELECT * FROM items WHERE id = ?", (item_id,)
        )
        row = await cursor.fetchone()
        return Item.from_row(dict(row)) if row else None

    async def get_items_by_source(
        self,
        source_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Item]:
        """Get items from a specific source, ordered by published_at DESC."""
        assert self._conn is not None
        cursor = await self._conn.execute(
            """SELECT * FROM items WHERE source_id = ?
               ORDER BY published_at DESC LIMIT ? OFFSET ?""",
            (source_id, limit, offset),
        )
        rows = await cursor.fetchall()
        return [Item.from_row(dict(r)) for r in rows]

    async def get_items_by_category(
        self,
        category: str,
        since: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[Item]:
        """Get items by category, optionally filtered by date."""
        assert self._conn is not None
        if since:
            cursor = await self._conn.execute(
                """SELECT * FROM items WHERE category = ? AND published_at >= ?
                   ORDER BY published_at DESC LIMIT ?""",
                (category, since.isoformat(), limit),
            )
        else:
            cursor = await self._conn.execute(
                """SELECT * FROM items WHERE category = ?
                   ORDER BY published_at DESC LIMIT ?""",
                (category, limit),
            )
        rows = await cursor.fetchall()
        return [Item.from_row(dict(r)) for r in rows]

    async def item_exists(self, item_id: str) -> bool:
        """Check if an item already exists."""
        assert self._conn is not None
        cursor = await self._conn.execute(
            "SELECT 1 FROM items WHERE id = ?", (item_id,)
        )
        return await cursor.fetchone() is not None

    async def url_canonical_exists(self, url_canonical: str) -> bool:
        """Check if a canonical URL already exists (cross-source dedup)."""
        assert self._conn is not None
        cursor = await self._conn.execute(
            "SELECT 1 FROM items WHERE url_canonical = ?", (url_canonical,)
        )
        return await cursor.fetchone() is not None

    async def count_items(self, source_id: Optional[str] = None) -> int:
        """Count items, optionally filtered by source."""
        assert self._conn is not None
        if source_id:
            cursor = await self._conn.execute(
                "SELECT COUNT(*) FROM items WHERE source_id = ?", (source_id,)
            )
        else:
            cursor = await self._conn.execute("SELECT COUNT(*) FROM items")
        row = await cursor.fetchone()
        return row[0] if row else 0

    # --- Search ---

    async def search(
        self,
        query: str,
        category: Optional[str] = None,
        language: Optional[str] = None,
        source_id: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = DEFAULT_SEARCH_LIMIT,
        offset: int = 0,
    ) -> List[Item]:
        """Full-text search with optional filters. Uses FTS5 BM25 ranking."""
        assert self._conn is not None

        # Build the query using FTS5 MATCH with joins for filtering
        conditions = []
        params: list = []

        # FTS match
        conditions.append("items_fts MATCH ?")
        params.append(query)

        # Optional filters on the items table
        if category:
            conditions.append("i.category = ?")
            params.append(category)
        if language:
            conditions.append("i.language = ?")
            params.append(language)
        if source_id:
            conditions.append("i.source_id = ?")
            params.append(source_id)
        if since:
            conditions.append("i.published_at >= ?")
            params.append(since.isoformat())

        where = " AND ".join(conditions)
        params.extend([limit, offset])

        sql = f"""
            SELECT i.*, bm25(items_fts, 1.0, 0.5) AS rank
            FROM items_fts
            JOIN items i ON i.rowid = items_fts.rowid
            WHERE {where}
            ORDER BY rank
            LIMIT ? OFFSET ?
        """

        t0 = time.monotonic()
        cursor = await self._conn.execute(sql, params)
        rows = await cursor.fetchall()
        elapsed = time.monotonic() - t0

        logger.debug("FTS search for %r: %d results in %.3fs", query, len(rows), elapsed)
        return [Item.from_row(dict(r)) for r in rows]

    async def search_count(self, query: str) -> int:
        """Count total FTS results for a query (for pagination)."""
        assert self._conn is not None
        cursor = await self._conn.execute(
            "SELECT COUNT(*) FROM items_fts WHERE items_fts MATCH ?",
            (query,),
        )
        row = await cursor.fetchone()
        return row[0] if row else 0

    # --- Metrics ---

    async def upsert_metrics(self, metrics: List[Metric]) -> int:
        """Insert or update metrics in batch."""
        if not metrics:
            return 0

        inserted = 0
        async with self._transaction() as conn:
            for i in range(0, len(metrics), self.batch_size):
                batch = metrics[i : i + self.batch_size]
                rows = [m.to_row() for m in batch]
                cursor = await conn.executemany(
                    """INSERT OR REPLACE INTO metrics
                       (item_id, score, score_authority, score_recency, score_popularity,
                        score_relevance, dup_penalty, cluster_id, summary_json, computed_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    rows,
                )
                inserted += cursor.rowcount

        return inserted

    async def get_top_items(
        self,
        category: Optional[str] = None,
        limit: int = 20,
        since: Optional[datetime] = None,
    ) -> List[Tuple[Item, Metric]]:
        """Get top-scored items with their metrics."""
        assert self._conn is not None

        conditions = ["m.score IS NOT NULL"]
        params: list = []

        if category:
            conditions.append("i.category = ?")
            params.append(category)
        if since:
            conditions.append("i.published_at >= ?")
            params.append(since.isoformat())

        where = " AND ".join(conditions)
        params.append(limit)

        cursor = await self._conn.execute(
            f"""SELECT i.*, m.score, m.score_authority, m.score_recency,
                       m.score_popularity, m.score_relevance, m.dup_penalty,
                       m.cluster_id, m.summary_json, m.computed_at
                FROM items i
                JOIN metrics m ON m.item_id = i.id
                WHERE {where}
                ORDER BY m.score DESC
                LIMIT ?""",
            params,
        )
        rows = await cursor.fetchall()

        results = []
        for r in rows:
            d = dict(r)
            item = Item.from_row(d)
            metric = Metric.from_row({
                "item_id": d["id"],
                "score": d["score"],
                "score_authority": d["score_authority"],
                "score_recency": d["score_recency"],
                "score_popularity": d["score_popularity"],
                "score_relevance": d["score_relevance"],
                "dup_penalty": d["dup_penalty"],
                "cluster_id": d["cluster_id"],
                "summary_json": d["summary_json"],
                "computed_at": d["computed_at"],
            })
            results.append((item, metric))

        return results

    # --- Digests ---

    async def save_digest(self, digest: Digest) -> int:
        """Save or update a digest section. Returns the digest ID."""
        assert self._conn is not None
        async with self._write_lock:
            cursor = await self._conn.execute(
                """INSERT INTO digests (date, section, content_markdown, content_json)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(date, section) DO UPDATE SET
                       content_markdown=excluded.content_markdown,
                       content_json=excluded.content_json,
                       generated_at=CURRENT_TIMESTAMP""",
                digest.to_row(),
            )
            await self._conn.commit()
            return cursor.lastrowid or 0

    async def get_digest(self, date: str, section: Optional[str] = None) -> List[Digest]:
        """Get digest(s) for a date, optionally filtered by section."""
        assert self._conn is not None
        if section:
            cursor = await self._conn.execute(
                "SELECT * FROM digests WHERE date = ? AND section = ?",
                (date, section),
            )
        else:
            cursor = await self._conn.execute(
                "SELECT * FROM digests WHERE date = ? ORDER BY section",
                (date,),
            )
        rows = await cursor.fetchall()
        return [Digest.from_row(dict(r)) for r in rows]

    # --- Maintenance ---

    async def vacuum(self) -> None:
        """Run VACUUM to reclaim space and defragment."""
        assert self._conn is not None
        async with self._write_lock:
            await self._conn.execute("VACUUM")

    async def optimize_fts(self) -> None:
        """Optimize the FTS5 index for better search performance."""
        assert self._conn is not None
        async with self._write_lock:
            await self._conn.execute("INSERT INTO items_fts(items_fts) VALUES('optimize')")
            await self._conn.commit()

    async def integrity_check(self) -> bool:
        """Run integrity check on the database."""
        assert self._conn is not None
        cursor = await self._conn.execute("PRAGMA integrity_check")
        row = await cursor.fetchone()
        return row is not None and row[0] == "ok"

    async def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        assert self._conn is not None
        stats: Dict[str, Any] = {}

        cursor = await self._conn.execute("SELECT COUNT(*) FROM items")
        row = await cursor.fetchone()
        stats["total_items"] = row[0] if row else 0

        cursor = await self._conn.execute("SELECT COUNT(*) FROM sources")
        row = await cursor.fetchone()
        stats["total_sources"] = row[0] if row else 0

        cursor = await self._conn.execute("SELECT COUNT(*) FROM metrics")
        row = await cursor.fetchone()
        stats["total_metrics"] = row[0] if row else 0

        cursor = await self._conn.execute("SELECT COUNT(*) FROM digests")
        row = await cursor.fetchone()
        stats["total_digests"] = row[0] if row else 0

        cursor = await self._conn.execute(
            """SELECT category, COUNT(*) as cnt FROM items
               GROUP BY category ORDER BY cnt DESC"""
        )
        stats["items_by_category"] = {r["category"]: r["cnt"] for r in await cursor.fetchall()}

        cursor = await self._conn.execute(
            """SELECT source_id, COUNT(*) as cnt FROM items
               GROUP BY source_id ORDER BY cnt DESC"""
        )
        stats["items_by_source"] = {r["source_id"]: r["cnt"] for r in await cursor.fetchall()}

        cursor = await self._conn.execute(
            "SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()"
        )
        row = await cursor.fetchone()
        stats["db_size_bytes"] = row[0] if row else 0

        return stats
