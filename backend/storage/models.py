"""Data models for the AI News Platform storage layer."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, urlunparse

# Use shared canonical URL logic with denoise layer for consistent dedup
def _canonicalize_url(url: str) -> str:
    from backend.denoise.dedup import canonical_url
    return canonical_url(url)


@dataclass
class Source:
    """A content source configuration and its runtime status."""

    id: str
    config: Dict[str, Any]
    last_fetch_at: Optional[datetime] = None
    last_error: Optional[str] = None
    error_count: int = 0
    enabled: bool = True
    created_at: Optional[datetime] = None

    @classmethod
    def from_config(cls, cfg: Dict[str, Any]) -> Source:
        """Create a Source from a config.yaml entry."""
        return cls(id=cfg["id"], config=cfg, enabled=True)

    def to_row(self) -> tuple:
        return (
            self.id,
            json.dumps(self.config),
            self.last_fetch_at.isoformat() if self.last_fetch_at else None,
            self.last_error,
            self.error_count,
            int(self.enabled),
        )

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> Source:
        return cls(
            id=row["id"],
            config=json.loads(row["config"]) if isinstance(row["config"], str) else row["config"],
            last_fetch_at=_parse_ts(row.get("last_fetch_at")),
            last_error=row.get("last_error"),
            error_count=row.get("error_count", 0),
            enabled=bool(row.get("enabled", 1)),
            created_at=_parse_ts(row.get("created_at")),
        )


@dataclass
class Item:
    """A single content item (article, paper, tip)."""

    id: str
    source_id: str
    url: str
    url_canonical: str
    title: str
    published_at: datetime
    category: str
    language: str
    external_id: Optional[str] = None
    content: Optional[str] = None
    author: Optional[str] = None
    ingested_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None
    snapshot_path: Optional[str] = None

    @staticmethod
    def make_id(url: str, source_id: str) -> str:
        """Generate a deterministic item ID from URL + source."""
        raw = f"{source_id}:{url}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()[:16]

    @staticmethod
    def canonicalize_url(url: str) -> str:
        """Normalize URL for deduplication (matches denoise.dedup.canonical_url)."""
        return _canonicalize_url(url)

    def to_row(self) -> tuple:
        return (
            self.id,
            self.source_id,
            self.external_id,
            self.url,
            self.url_canonical,
            self.title,
            self.content,
            self.author,
            self.published_at.isoformat() if self.published_at else None,
            self.ingested_at.isoformat() if self.ingested_at else None,
            self.category,
            self.language,
            json.dumps(self.metadata) if self.metadata else None,
            self.snapshot_path,
        )

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> Item:
        return cls(
            id=row["id"],
            source_id=row["source_id"],
            external_id=row.get("external_id"),
            url=row["url"],
            url_canonical=row["url_canonical"],
            title=row["title"],
            content=row.get("content"),
            author=row.get("author"),
            published_at=_parse_ts(row["published_at"]) or datetime.min,
            ingested_at=_parse_ts(row.get("ingested_at")),
            category=row["category"],
            language=row["language"],
            metadata=_parse_json(row.get("metadata")),
            snapshot_path=row.get("snapshot_path"),
        )


@dataclass
class Metric:
    """Scoring metrics for an item."""

    item_id: str
    score: float
    score_authority: Optional[float] = None
    score_recency: Optional[float] = None
    score_popularity: Optional[float] = None
    score_relevance: Optional[float] = None
    dup_penalty: Optional[float] = None
    cluster_id: Optional[str] = None
    summary_json: Optional[Dict[str, Any]] = None
    computed_at: Optional[datetime] = None

    def to_row(self) -> tuple:
        return (
            self.item_id,
            self.score,
            self.score_authority,
            self.score_recency,
            self.score_popularity,
            self.score_relevance,
            self.dup_penalty,
            self.cluster_id,
            json.dumps(self.summary_json) if self.summary_json else None,
            self.computed_at.isoformat() if self.computed_at else None,
        )

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> Metric:
        return cls(
            item_id=row["item_id"],
            score=row["score"],
            score_authority=row.get("score_authority"),
            score_recency=row.get("score_recency"),
            score_popularity=row.get("score_popularity"),
            score_relevance=row.get("score_relevance"),
            dup_penalty=row.get("dup_penalty"),
            cluster_id=row.get("cluster_id"),
            summary_json=_parse_json(row.get("summary_json")),
            computed_at=_parse_ts(row.get("computed_at")),
        )


@dataclass
class Digest:
    """A generated daily digest section."""

    id: Optional[int]
    date: str
    section: str
    content_markdown: str
    content_json: Dict[str, Any]
    generated_at: Optional[datetime] = None

    def to_row(self) -> tuple:
        return (
            self.date,
            self.section,
            self.content_markdown,
            json.dumps(self.content_json),
        )

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> Digest:
        return cls(
            id=row.get("id"),
            date=row["date"],
            section=row["section"],
            content_markdown=row["content_markdown"],
            content_json=_parse_json(row.get("content_json")) or {},
            generated_at=_parse_ts(row.get("generated_at")),
        )


@dataclass
class IngestResult:
    """Result from an ingest run."""

    source_id: str
    fetched: int = 0
    inserted: int = 0
    duplicates: int = 0
    errors: int = 0
    duration_seconds: float = 0.0
    error_message: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.error_message is None


@dataclass
class IngestSummary:
    """Aggregate result from a full ingest run."""

    results: List[IngestResult] = field(default_factory=list)
    total_fetched: int = 0
    total_inserted: int = 0
    total_duplicates: int = 0
    total_errors: int = 0
    duration_seconds: float = 0.0

    def add(self, result: IngestResult) -> None:
        self.results.append(result)
        self.total_fetched += result.fetched
        self.total_inserted += result.inserted
        self.total_duplicates += result.duplicates
        self.total_errors += result.errors


# --- Helpers ---

def _parse_ts(val: Any) -> Optional[datetime]:
    """Parse a timestamp string or return None."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    try:
        from dateutil.parser import parse
        return parse(str(val))
    except (ValueError, TypeError):
        return None


def _parse_json(val: Any) -> Optional[Dict[str, Any]]:
    """Parse a JSON string or return None."""
    if val is None:
        return None
    if isinstance(val, dict):
        return val
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return None
