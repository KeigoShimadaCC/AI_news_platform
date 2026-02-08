"""Parallel ingest orchestrator for the AI News Platform.

Coordinates concurrent fetching from all enabled sources, normalizes items,
deduplicates URLs, performs batch inserts, and saves snapshots.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol

import yaml

from backend.storage.db import DatabaseManager
from backend.storage.models import IngestResult, IngestSummary, Item, Source

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = "config.yaml"
DEFAULT_DB_PATH = "data/ainews.db"
DEFAULT_SNAPSHOT_DIR = "data/snapshots"
DEFAULT_MAX_CONCURRENT = 10
DEFAULT_TIMEOUT = 30


class Connector(Protocol):
    """Protocol for source connectors (implemented by Agent A)."""

    async def fetch(self, source: Source) -> List[Dict[str, Any]]:
        """Fetch raw items from a source. Returns list of dicts."""
        ...


class SnapshotManager:
    """Save HTML snapshots to disk: data/snapshots/{source_id}/{date}/{hash}.html"""

    def __init__(self, base_dir: str = DEFAULT_SNAPSHOT_DIR):
        self.base_dir = Path(base_dir)

    def save(self, source_id: str, url: str, content: str) -> str:
        """Save content snapshot and return the relative path."""
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]

        dir_path = self.base_dir / source_id / date_str
        dir_path.mkdir(parents=True, exist_ok=True)

        file_path = dir_path / f"{url_hash}.html"
        file_path.write_text(content, encoding="utf-8")

        # Return relative path from project root
        return str(file_path)

    def exists(self, source_id: str, url: str) -> bool:
        """Check if a snapshot already exists for today."""
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]
        file_path = self.base_dir / source_id / date_str / f"{url_hash}.html"
        return file_path.exists()


class IngestOrchestrator:
    """Orchestrates parallel ingestion from all configured sources.

    Usage:
        orchestrator = IngestOrchestrator()
        summary = await orchestrator.ingest_all()
    """

    def __init__(
        self,
        config_path: str = DEFAULT_CONFIG_PATH,
        db_path: str = DEFAULT_DB_PATH,
        snapshot_dir: str = DEFAULT_SNAPSHOT_DIR,
        connector_factory: Optional[Callable[[Dict[str, Any]], Connector]] = None,
        max_concurrent: int = DEFAULT_MAX_CONCURRENT,
        request_timeout: int = DEFAULT_TIMEOUT,
    ):
        self.config_path = config_path
        self.db_path = db_path
        self.snapshot_dir = snapshot_dir
        self.connector_factory = connector_factory
        self.max_concurrent = max_concurrent
        self.request_timeout = request_timeout
        self.db: Optional[DatabaseManager] = None
        self.snapshots = SnapshotManager(snapshot_dir)

    def load_config(self) -> Dict[str, Any]:
        """Load and return the YAML configuration."""
        with open(self.config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    async def initialize(self) -> None:
        """Initialize database and load config."""
        self.db = DatabaseManager(self.db_path)
        await self.db.initialize()

    async def close(self) -> None:
        """Close database connection."""
        if self.db:
            await self.db.close()

    async def ingest_all(self, source_ids: Optional[List[str]] = None) -> IngestSummary:
        """Ingest from all enabled sources (or specified subset) concurrently.

        Steps:
            1. Load sources from config + DB
            2. Create connectors
            3. Fetch concurrently with error handling
            4. Normalize & deduplicate URLs
            5. Batch insert to DB
            6. Save snapshots to disk
            7. Update source status
        """
        if not self.db:
            await self.initialize()
        assert self.db is not None

        config = self.load_config()
        summary = IngestSummary()
        t0 = time.monotonic()

        # Step 1: Load sources from config, then filter by DB enabled flag
        sources = self._get_sources(config, source_ids)
        disabled_ids = await self.db.get_disabled_source_ids()
        sources = [s for s in sources if s.id not in disabled_ids]
        if not sources:
            logger.warning("No sources to ingest (none enabled or none match filter)")
            return summary

        # Sync sources to DB (preserves existing enabled flag on update)
        for source in sources:
            await self.db.upsert_source(source)

        # Step 2-7: Ingest concurrently with semaphore
        sem = asyncio.Semaphore(self.max_concurrent)
        tasks = [
            self._ingest_source(source, sem)
            for source in sources
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                logger.error("Ingest task failed: %s", result)
                summary.total_errors += 1
            elif isinstance(result, IngestResult):
                summary.add(result)

        summary.duration_seconds = time.monotonic() - t0
        logger.info(
            "Ingest complete: %d fetched, %d inserted, %d duplicates, %d errors in %.1fs",
            summary.total_fetched,
            summary.total_inserted,
            summary.total_duplicates,
            summary.total_errors,
            summary.duration_seconds,
        )
        return summary

    async def _ingest_source(
        self, source: Source, sem: asyncio.Semaphore
    ) -> IngestResult:
        """Ingest a single source with semaphore-based concurrency control."""
        assert self.db is not None
        result = IngestResult(source_id=source.id)
        t0 = time.monotonic()

        async with sem:
            try:
                # Fetch raw items
                raw_items = await self._fetch_source(source)
                result.fetched = len(raw_items)

                if not raw_items:
                    await self.db.update_source_status(
                        source.id, last_fetch_at=datetime.utcnow()
                    )
                    result.duration_seconds = time.monotonic() - t0
                    return result

                # Normalize to Item objects
                items = self._normalize_items(raw_items, source)

                # Deduplicate by canonical URL
                items, dups = await self._deduplicate(items)
                result.duplicates = dups

                # Batch insert
                inserted = await self.db.batch_insert_items(items)
                result.inserted = inserted

                # Save snapshots for items that have content
                for item in items:
                    if item.content:
                        try:
                            path = self.snapshots.save(
                                source.id, item.url, item.content
                            )
                            item.snapshot_path = path
                        except Exception as e:
                            logger.warning("Snapshot save failed for %s: %s", item.url, e)

                # Update source status
                await self.db.update_source_status(
                    source.id, last_fetch_at=datetime.utcnow()
                )

                logger.info(
                    "Source %s: fetched=%d, inserted=%d, dups=%d",
                    source.id, result.fetched, result.inserted, result.duplicates,
                )

            except Exception as e:
                result.error_message = str(e)
                result.errors = 1
                logger.error("Source %s failed: %s", source.id, e)
                await self.db.update_source_status(
                    source.id,
                    last_fetch_at=datetime.utcnow(),
                    last_error=str(e),
                    increment_errors=True,
                )

        result.duration_seconds = time.monotonic() - t0
        return result

    async def _fetch_source(self, source: Source) -> List[Dict[str, Any]]:
        """Fetch items from a source using its connector."""
        if self.connector_factory is None:
            # No connector available yet - return empty
            logger.warning(
                "No connector factory registered; skipping source %s", source.id
            )
            return []

        connector = self.connector_factory(source.config)
        try:
            return await asyncio.wait_for(
                connector.fetch(source),
                timeout=self.request_timeout,
            )
        except asyncio.TimeoutError:
            raise TimeoutError(
                f"Source {source.id} fetch timed out after {self.request_timeout}s"
            )

    def _normalize_items(
        self, raw_items: List[Dict[str, Any]], source: Source
    ) -> List[Item]:
        """Convert raw dicts to Item objects with canonical URLs."""
        items = []
        now = datetime.utcnow()

        for raw in raw_items:
            url = raw.get("url", "")
            if not url:
                continue

            canonical = Item.canonicalize_url(url)
            item_id = Item.make_id(url, source.id)

            try:
                item = Item(
                    id=item_id,
                    source_id=source.id,
                    external_id=raw.get("external_id"),
                    url=url,
                    url_canonical=canonical,
                    title=raw.get("title", "Untitled"),
                    content=raw.get("content"),
                    author=raw.get("author"),
                    published_at=_parse_datetime(raw.get("published_at")) or now,
                    ingested_at=now,
                    category=source.config.get("category", "news"),
                    language=source.config.get("lang", "en"),
                    metadata=raw.get("metadata"),
                )
                items.append(item)
            except Exception as e:
                logger.warning("Failed to normalize item %s: %s", url, e)

        return items

    async def _deduplicate(self, items: List[Item]) -> tuple:
        """Remove items with duplicate canonical URLs (both in-batch and in-DB).

        Returns (unique_items, duplicate_count).
        """
        assert self.db is not None
        seen: set = set()
        unique = []
        dups = 0

        for item in items:
            if item.url_canonical in seen:
                dups += 1
                continue

            # Check DB for existing canonical URL
            if await self.db.url_canonical_exists(item.url_canonical):
                dups += 1
                seen.add(item.url_canonical)
                continue

            seen.add(item.url_canonical)
            unique.append(item)

        return unique, dups

    def _get_sources(
        self,
        config: Dict[str, Any],
        source_ids: Optional[List[str]] = None,
    ) -> List[Source]:
        """Build Source objects from config, optionally filtering by ID."""
        sources = []
        for cfg in config.get("sources", []):
            source = Source.from_config(cfg)
            if source_ids and source.id not in source_ids:
                continue
            sources.append(source)
        return sources


def _parse_datetime(val: Any) -> Optional[datetime]:
    """Parse various datetime formats."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    try:
        from dateutil.parser import parse
        return parse(str(val))
    except (ValueError, TypeError):
        return None
