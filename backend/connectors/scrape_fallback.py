"""Scrape fallback: fetch HTML and extract links/titles for when RSS fails."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import TYPE_CHECKING, Any, Dict, List

import aiohttp
from bs4 import BeautifulSoup
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

if TYPE_CHECKING:
    from backend.storage.models import Source

logger = logging.getLogger(__name__)

DEFAULT_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


class ScrapeFallbackConnector:
    """Fetch a page and extract article-like links and titles. Used as fallback when RSS fails."""

    def __init__(self, config: Dict[str, Any]) -> None:
        self.url = config.get("url", "")
        self.user_agent = config.get("user_agent") or DEFAULT_USER_AGENT
        self.base_url = self._base_from_url(self.url)

    @staticmethod
    def _base_from_url(url: str) -> str:
        from urllib.parse import urljoin, urlparse
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"

    @retry(
        retry=retry_if_exception_type((aiohttp.ClientError, OSError, ConnectionError)),
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    )
    async def fetch(self, source: "Source") -> List[Dict[str, Any]]:
        """Fetch URL as HTML and extract links with titles."""
        url = self.url or source.config.get("url", "")
        if not url:
            return []

        headers = {"User-Agent": self.user_agent or source.config.get("user_agent") or DEFAULT_USER_AGENT}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                resp.raise_for_status()
                html = await resp.text()

        return await self._parse_html(html, url, source)

    async def _parse_html(self, html: str, page_url: str, source: "Source") -> List[Dict[str, Any]]:
        """Parse HTML and yield raw item dicts (url, title, content snippet)."""
        from urllib.parse import urljoin
        loop = asyncio.get_event_loop()
        def _parse() -> List[Dict[str, Any]]:
            soup = BeautifulSoup(html, "lxml")
            base = self._base_from_url(page_url)
            items: List[Dict[str, Any]] = []
            seen: set[str] = set()
            # Common patterns: article links, list items with links
            for a in soup.find_all("a", href=True):
                href = a.get("href", "").strip()
                if not href or href.startswith("#") or href.startswith("mailto:"):
                    continue
                full_url = urljoin(base, href)
                if full_url in seen:
                    continue
                title = (a.get_text(strip=True) or "").strip()
                if len(title) < 3 or len(title) > 500:
                    continue
                # Skip nav/footer/common links
                if _is_noise(href, title):
                    continue
                seen.add(full_url)
                items.append({
                    "url": full_url,
                    "title": title[:500],
                    "content": "",
                    "author": None,
                    "published_at": None,
                    "metadata": {},
                    "external_id": full_url,
                })
            return items[:100]
        return await loop.run_in_executor(None, _parse)


def _is_noise(href: str, title: str) -> bool:
    """Skip navigation and non-article links."""
    noise = (
        "login", "signup", "twitter", "facebook", "github.com", "linkedin",
        "mailto", "javascript:", "tel:", "cookie", "privacy", "terms",
        "tag/", "tags/", "category/", "author/", "page/", "search",
        "rss", "feed", ".xml", ".json", "#",
    )
    lower = (href + " " + title).lower()
    return any(n in lower for n in noise)
