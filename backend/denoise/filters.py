"""Hard filters: keyword exclusion, language filtering, and popularity thresholds."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ItemRecord:
    """Lightweight item representation used throughout the denoise pipeline.

    Mirrors the DB ``items`` table with parsed metadata.
    """

    id: str
    source_id: str
    url: str
    title: str
    content: str
    author: str | None
    published_at: str
    fetched_at: str
    lang: str
    category: str  # "news" | "tips" | "paper"
    metadata: dict[str, Any] = field(default_factory=dict)

    # Populated during scoring / dedup
    cluster_id: str | None = None
    is_representative: bool = False

    @classmethod
    def from_db_row(cls, row: dict[str, Any]) -> ItemRecord:
        """Create from a DB row dict (items table)."""
        meta_raw = row.get("metadata_json") or "{}"
        if isinstance(meta_raw, str):
            try:
                meta = json.loads(meta_raw)
            except (json.JSONDecodeError, TypeError):
                meta = {}
        else:
            meta = meta_raw
        return cls(
            id=row["id"],
            source_id=row["source_id"],
            url=row["url"],
            title=row.get("title", ""),
            content=row.get("content", ""),
            author=row.get("author"),
            published_at=row.get("published_at", ""),
            fetched_at=row.get("fetched_at", ""),
            lang=row.get("lang", "en"),
            category=row.get("category", "news"),
            metadata=meta,
        )


class HardFilter:
    """Apply hard (boolean) filters that immediately discard items."""

    def __init__(self, config: dict[str, Any]) -> None:
        scoring = config.get("scoring", {})
        self._exclude_patterns = [
            re.compile(re.escape(kw), re.IGNORECASE)
            for kw in scoring.get("keywords_exclude", [])
        ]
        self._min_popularity: dict[str, dict[str, int]] = scoring.get("min_popularity", {})

        # Build source→lang mapping from config sources
        self._source_lang: dict[str, str] = {}
        for src in config.get("sources", []):
            self._source_lang[src["id"]] = src.get("lang", "en")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def apply_all(self, items: list[ItemRecord]) -> list[ItemRecord]:
        """Run every hard filter in sequence and return surviving items."""
        before = len(items)
        items = self.filter_keywords(items)
        items = self.filter_language(items)
        items = self.filter_popularity(items)
        logger.info("HardFilter: %d → %d items", before, len(items))
        return items

    def filter_keywords(self, items: list[ItemRecord]) -> list[ItemRecord]:
        """Exclude items whose title or content matches any excluded keyword."""
        if not self._exclude_patterns:
            return items
        result: list[ItemRecord] = []
        for item in items:
            text = f"{item.title} {item.content}"
            if not any(pat.search(text) for pat in self._exclude_patterns):
                result.append(item)
        return result

    def filter_language(self, items: list[ItemRecord]) -> list[ItemRecord]:
        """Keep only items whose lang matches the source's declared language."""
        result: list[ItemRecord] = []
        for item in items:
            expected = self._source_lang.get(item.source_id)
            if expected is None or item.lang == expected:
                result.append(item)
        return result

    def filter_popularity(self, items: list[ItemRecord]) -> list[ItemRecord]:
        """Drop items below per-source popularity thresholds."""
        if not self._min_popularity:
            return items
        result: list[ItemRecord] = []
        for item in items:
            thresholds = self._min_popularity.get(item.source_id)
            if thresholds is None:
                result.append(item)
                continue
            passes = True
            for metric_key, min_val in thresholds.items():
                actual = item.metadata.get(metric_key, 0)
                if isinstance(actual, (int, float)) and actual < min_val:
                    passes = False
                    break
            if passes:
                result.append(item)
        return result
