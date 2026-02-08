"""RSS connector using feedparser with retry and optional user-agent."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, List

import feedparser
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

if TYPE_CHECKING:
    from backend.storage.models import Source

logger = logging.getLogger(__name__)

# Browser-like UA so more feeds (DeepMind, Zenn, arXiv, Reddit) accept requests
DEFAULT_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def _parse_entry(entry: Any, source_id: str, default_lang: str) -> Dict[str, Any] | None:
    """Convert a feedparser entry to a raw item dict."""
    link = getattr(entry, "link", None) or (entry.get("links", [{}])[0].get("href") if entry.get("links") else None)
    if not link:
        return None
    title = getattr(entry, "title", None) or "Untitled"
    if isinstance(title, bytes):
        title = title.decode("utf-8", errors="replace")
    content = getattr(entry, "summary", None) or getattr(entry, "description", None) or ""
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")
    author = getattr(entry, "author", None)
    published = getattr(entry, "published", None) or getattr(entry, "updated", None)
    return {
        "url": link,
        "title": title,
        "content": content,
        "author": author,
        "published_at": published,
        "metadata": {},
        "external_id": getattr(entry, "id", None) or link,
    }


class RSSConnector:
    """Fetch items from an RSS/Atom feed."""

    def __init__(self, config: Dict[str, Any]) -> None:
        self.url = config.get("url", "")
        self.user_agent = config.get("user_agent") or DEFAULT_USER_AGENT
        self.lang = config.get("lang", "en")

    @retry(
        retry=retry_if_exception_type((OSError, ConnectionError, TimeoutError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        reraise=True,
    )
    async def fetch(self, source: "Source") -> List[Dict[str, Any]]:
        """Fetch and parse RSS feed. Runs in executor to avoid blocking."""
        import asyncio
        url = self.url or source.config.get("url", "")
        if not url:
            logger.warning("RSS source %s has no url", source.id)
            return []

        def _parse() -> List[Dict[str, Any]]:
            feed = feedparser.parse(
                url,
                request_headers={"User-Agent": self.user_agent},
                response_headers=True,
            )
            entries = getattr(feed, "entries", [])
            # Only raise on parse error if we got no entries; minor bozo with entries is OK
            if getattr(feed, "bozo", False) and feed.bozo_exception and not entries:
                raise feed.bozo_exception
            items: List[Dict[str, Any]] = []
            for entry in entries:
                row = _parse_entry(entry, source.id, self.lang)
                if row:
                    items.append(row)
            return items

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _parse)
