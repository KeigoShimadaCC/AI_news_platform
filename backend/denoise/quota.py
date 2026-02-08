"""Quota enforcement: per-source and per-category limits."""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from backend.denoise.filters import ItemRecord
from backend.denoise.scorer import ScoreBreakdown

logger = logging.getLogger(__name__)


class QuotaManager:
    """Enforce per-source quotas and per-category limits on scored items."""

    def __init__(self, config: dict[str, Any]) -> None:
        scoring = config.get("scoring", {})
        self._source_quotas: dict[str, int] = scoring.get("quotas", {})
        self._default_quota: int = self._source_quotas.pop("default", 20)

        digest = config.get("digest", {})
        self._category_limits: dict[str, int] = digest.get("limits", {
            "news": 20, "tips": 20, "paper": 10,
        })

    def apply_quotas(
        self,
        scored_items: list[tuple[ItemRecord, ScoreBreakdown]],
    ) -> list[tuple[ItemRecord, ScoreBreakdown]]:
        """Apply per-source quotas then per-category limits.

        Items must already be sorted by score descending for greedy top-N.
        """
        # Phase 1: per-source quota
        source_counts: dict[str, int] = defaultdict(int)
        after_source: list[tuple[ItemRecord, ScoreBreakdown]] = []

        for item, bd in scored_items:
            quota = self._source_quotas.get(item.source_id, self._default_quota)
            if source_counts[item.source_id] < quota:
                after_source.append((item, bd))
                source_counts[item.source_id] += 1

        # Phase 2: per-category limit
        cat_counts: dict[str, int] = defaultdict(int)
        result: list[tuple[ItemRecord, ScoreBreakdown]] = []

        for item, bd in after_source:
            limit = self._category_limits.get(item.category, 20)
            if cat_counts[item.category] < limit:
                result.append((item, bd))
                cat_counts[item.category] += 1

        logger.info(
            "QuotaManager: %d → %d items (source quotas + category limits)",
            len(scored_items),
            len(result),
        )
        return result
