"""RSS with scrape fallback: try RSS first, on failure try scraping the URL."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, List

from backend.connectors.rss import RSSConnector
from backend.connectors.scrape_fallback import ScrapeFallbackConnector

if TYPE_CHECKING:
    from backend.storage.models import Source

logger = logging.getLogger(__name__)


class RSSOrScrapeConnector:
    """Try RSS first; if it fails (parse error, empty, or exception), fall back to scrape."""

    def __init__(self, config: Dict[str, Any]) -> None:
        self._rss = RSSConnector(config)
        self._scrape = ScrapeFallbackConnector(config)

    async def fetch(self, source: "Source") -> List[Dict[str, Any]]:
        """Fetch via RSS; on failure try scrape."""
        try:
            items = await self._rss.fetch(source)
            if items:
                return items
        except Exception as e:
            logger.warning("RSS failed for %s (%s), trying scrape fallback", source.id, e)
        try:
            return await self._scrape.fetch(source)
        except Exception as e:
            logger.error("Scrape fallback failed for %s: %s", source.id, e)
            raise
