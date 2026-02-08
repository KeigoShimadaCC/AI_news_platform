"""Digest generator: orchestrates filters → dedup → score → quota → summarize."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

from backend.denoise.filters import HardFilter, ItemRecord
from backend.denoise.dedup import DedupClusterer
from backend.denoise.scorer import Scorer, ScoreBreakdown
from backend.denoise.quota import QuotaManager
from backend.digest.summarizer import LLMSummarizer

logger = logging.getLogger(__name__)


@dataclass
class DigestItem:
    """A scored item with its summary, ready for presentation."""

    item: ItemRecord
    score: ScoreBreakdown
    summary: str = ""


@dataclass
class Digest:
    """The final daily digest, grouped by category."""

    date: str
    news: list[DigestItem] = field(default_factory=list)
    tips: list[DigestItem] = field(default_factory=list)
    papers: list[DigestItem] = field(default_factory=list)

    @property
    def total_items(self) -> int:
        return len(self.news) + len(self.tips) + len(self.papers)

    def to_dict(self) -> dict[str, Any]:
        def _section(items: list[DigestItem]) -> list[dict[str, Any]]:
            return [
                {
                    "id": di.item.id,
                    "source_id": di.item.source_id,
                    "url": di.item.url,
                    "title": di.item.title,
                    "author": di.item.author,
                    "published_at": di.item.published_at,
                    "category": di.item.category,
                    "lang": di.item.lang,
                    "cluster_id": di.item.cluster_id,
                    "summary": di.summary,
                    **di.score.to_dict(),
                }
                for di in items
            ]

        return {
            "date": self.date,
            "news": _section(self.news),
            "tips": _section(self.tips),
            "papers": _section(self.papers),
        }


class DigestGenerator:
    """End-to-end digest pipeline: filter → dedup → score → quota → summarize."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.hard_filter = HardFilter(config)
        self.dedup = DedupClusterer(config)
        self.scorer = Scorer(config)
        self.quota = QuotaManager(config)
        self.summarizer = LLMSummarizer(config)

    async def generate_digest(
        self,
        items: list[ItemRecord],
        digest_date: date | None = None,
    ) -> Digest:
        """Run the full pipeline on a list of raw items.

        Parameters
        ----------
        items:
            Raw items (e.g. from DB query for the day).
        digest_date:
            Date label for the digest. Defaults to today.
        """
        if digest_date is None:
            digest_date = datetime.now(timezone.utc).date()

        logger.info("DigestGenerator: starting with %d items for %s", len(items), digest_date)

        # 1. Hard filters
        filtered = self.hard_filter.apply_all(items)

        # 2. Deduplication
        clusters = self.dedup.cluster_items(filtered)

        # Flatten back, keeping cluster metadata on items
        deduped: list[ItemRecord] = []
        for cluster_items in clusters.values():
            deduped.extend(cluster_items)

        # 3. Score all items
        scored = self.scorer.score_items(deduped)

        # 4. Sort by score descending
        scored.sort(key=lambda x: x[1].total, reverse=True)

        # 5. Apply quotas
        final = self.quota.apply_quotas(scored)

        # 6. Generate summaries for top items
        top_items = [item for item, _ in final]
        summaries = await self.summarizer.summarize(top_items)

        # 7. Build digest
        digest = Digest(date=digest_date.isoformat())
        category_map = {"news": digest.news, "tips": digest.tips, "paper": digest.papers}

        for item, bd in final:
            di = DigestItem(
                item=item,
                score=bd,
                summary=summaries.get(item.id, ""),
            )
            target = category_map.get(item.category, digest.news)
            target.append(di)

        logger.info(
            "DigestGenerator: produced digest with %d items (news=%d, tips=%d, papers=%d)",
            digest.total_items,
            len(digest.news),
            len(digest.tips),
            len(digest.papers),
        )
        return digest
