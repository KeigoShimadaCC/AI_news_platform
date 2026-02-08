"""Multi-factor scoring with explainable breakdown."""

from __future__ import annotations

import math
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import numpy as np
from dateutil.parser import parse as dateparse

from backend.denoise.filters import ItemRecord

logger = logging.getLogger(__name__)


@dataclass
class ScoreBreakdown:
    """Explainable score with per-factor values (all in [0, 1])."""

    total: float
    authority: float
    recency: float
    popularity: float
    relevance: float
    dup_penalty: float

    def to_dict(self) -> dict[str, float]:
        return {
            "total": round(self.total, 4),
            "authority": round(self.authority, 4),
            "recency": round(self.recency, 4),
            "popularity": round(self.popularity, 4),
            "relevance": round(self.relevance, 4),
            "dup_penalty": round(self.dup_penalty, 4),
        }


# ---------------------------------------------------------------------------
# Relevance keywords (AI/ML domain)
# ---------------------------------------------------------------------------

_RELEVANCE_KEYWORDS = [
    r"\bLLM\b", r"\blarge language model\b", r"\bGPT\b", r"\btransformer\b",
    r"\bRAG\b", r"\bretrieval.augmented\b", r"\bagent\b", r"\bfine.?tun",
    r"\bembedding\b", r"\bvector\b", r"\bmultimodal\b", r"\bdiffusion\b",
    r"\breinforcement learning\b", r"\bneural\b", r"\bdeep learning\b",
    r"\bprompt\b", r"\bClaude\b", r"\bOpenAI\b", r"\bAnthrop", r"\bMCP\b",
    r"\bAI\b", r"\bmachine learning\b",
]
_RELEVANCE_PATTERNS = [re.compile(p, re.IGNORECASE) for p in _RELEVANCE_KEYWORDS]


def _get_raw_popularity(meta: dict[str, Any], source_id: str, field_hint: str | None) -> float:
    """Get raw popularity value from metadata. field_hint prefers a specific key when set."""
    if field_hint and isinstance(meta.get(field_hint), (int, float)):
        return float(meta[field_hint])
    for key in ("points", "score", "stars", "likes_count", "likes"):
        val = meta.get(key)
        if isinstance(val, (int, float)):
            return float(val)
    return 0.0


class Scorer:
    """Compute a weighted multi-factor score for each item."""

    def __init__(self, config: dict[str, Any]) -> None:
        weights = config.get("scoring", {}).get("weights", {})
        self.w_authority = weights.get("authority", 0.30)
        self.w_recency = weights.get("recency", 0.25)
        self.w_popularity = weights.get("popularity", 0.20)
        self.w_relevance = weights.get("relevance", 0.20)
        self.w_dup_penalty = weights.get("dup_penalty", 0.05)

        # Build source→authority map from config
        self._source_authority: dict[str, float] = {}
        for src in config.get("sources", []):
            self._source_authority[src["id"]] = src.get("authority", 0.5)

        # Per-source popularity field from min_popularity (e.g. hn_ai→points, github_ai_repos→stars)
        self._source_popularity_field: dict[str, str] = {}
        min_pop = config.get("scoring", {}).get("min_popularity", {})
        for src_id, thresh in min_pop.items():
            if isinstance(thresh, dict) and thresh:
                self._source_popularity_field[src_id] = next(iter(thresh.keys()))

        self._now = datetime.now(timezone.utc)
        self._batch_source_max: dict[str, float] = {}

    def score_item(self, item: ItemRecord) -> ScoreBreakdown:
        """Compute the full score breakdown for a single item."""
        authority = self._authority(item)
        recency = self._recency(item)
        popularity = self._popularity(item)
        relevance = self._relevance(item)
        dup_penalty = self._dup_penalty(item)

        total = (
            self.w_authority * authority
            + self.w_recency * recency
            + self.w_popularity * popularity
            + self.w_relevance * relevance
            - self.w_dup_penalty * dup_penalty
        )
        total = max(0.0, min(1.0, total))

        return ScoreBreakdown(
            total=total,
            authority=authority,
            recency=recency,
            popularity=popularity,
            relevance=relevance,
            dup_penalty=dup_penalty,
        )

    def score_items(self, items: list[ItemRecord]) -> list[tuple[ItemRecord, ScoreBreakdown]]:
        """Score a batch of items. Uses per-source popularity normalization (log1p + max)."""
        if not items:
            return []

        # Per-source max popularity for this batch (p95-style: cap then normalize)
        self._batch_source_max = {}
        for item in items:
            field_hint = self._source_popularity_field.get(item.source_id)
            raw = _get_raw_popularity(item.metadata, item.source_id, field_hint)
            if raw > 0:
                cur = self._batch_source_max.get(item.source_id, 0.0)
                self._batch_source_max[item.source_id] = max(cur, raw)
        for sid in self._batch_source_max:
            if self._batch_source_max[sid] < 1:
                self._batch_source_max[sid] = 1.0

        n = len(items)
        auth = np.empty(n)
        rec = np.empty(n)
        pop = np.empty(n)
        rel = np.empty(n)
        dup = np.empty(n)

        for i, item in enumerate(items):
            auth[i] = self._authority(item)
            rec[i] = self._recency(item)
            pop[i] = self._popularity(item)
            rel[i] = self._relevance(item)
            dup[i] = self._dup_penalty(item)

        totals = (
            self.w_authority * auth
            + self.w_recency * rec
            + self.w_popularity * pop
            + self.w_relevance * rel
            - self.w_dup_penalty * dup
        )
        totals = np.clip(totals, 0.0, 1.0)

        results: list[tuple[ItemRecord, ScoreBreakdown]] = []
        for i, item in enumerate(items):
            bd = ScoreBreakdown(
                total=float(totals[i]),
                authority=float(auth[i]),
                recency=float(rec[i]),
                popularity=float(pop[i]),
                relevance=float(rel[i]),
                dup_penalty=float(dup[i]),
            )
            results.append((item, bd))
        return results

    # ------------------------------------------------------------------
    # Factor computations
    # ------------------------------------------------------------------

    def _authority(self, item: ItemRecord) -> float:
        return self._source_authority.get(item.source_id, 0.5)

    def _recency(self, item: ItemRecord) -> float:
        """Exponential decay: exp(-days_ago / 7)."""
        try:
            pub = dateparse(item.published_at)
            if pub.tzinfo is None:
                pub = pub.replace(tzinfo=timezone.utc)
            days_ago = max(0.0, (self._now - pub).total_seconds() / 86400)
        except (ValueError, TypeError):
            days_ago = 30.0  # Unknown date → stale
        return math.exp(-days_ago / 7.0)

    def _popularity(self, item: ItemRecord) -> float:
        """Normalize popularity to [0, 1] per-source: log1p(raw) / log1p(max_for_source)."""
        field_hint = self._source_popularity_field.get(item.source_id)
        raw = _get_raw_popularity(item.metadata, item.source_id, field_hint)
        if raw <= 0:
            return 0.0
        max_for_source = self._batch_source_max.get(item.source_id)
        if max_for_source is None or max_for_source < 1:
            max_for_source = 1000.0
        return min(1.0, math.log1p(raw) / math.log1p(max_for_source))

    def _relevance(self, item: ItemRecord) -> float:
        """Keyword-based relevance score in [0, 1]."""
        text = f"{item.title} {item.content[:1000]}"
        matches = sum(1 for p in _RELEVANCE_PATTERNS if p.search(text))
        # Normalize: 3+ matches → 1.0
        return min(1.0, matches / 3.0)

    def _dup_penalty(self, item: ItemRecord) -> float:
        """0 for representative, 1.0 for non-representative duplicates."""
        if item.cluster_id is None:
            return 0.0
        return 0.0 if item.is_representative else 1.0
