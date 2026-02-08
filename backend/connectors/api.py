"""Generic API connector: GET request with params/headers, normalizes JSON to items."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, List

import aiohttp
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


class APIConnector:
    """Fetch items from a REST API. Subclasses or config define how to map response to items."""

    def __init__(self, config: Dict[str, Any]) -> None:
        self.url = config.get("url", "")
        self.params = config.get("params") or {}
        self.headers = self._resolve_headers(config.get("headers") or {})
        self.source_id = config.get("id", "")

    def _resolve_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """Resolve ${ENV_VAR} in header values (inline). Skip headers with empty resolved value (e.g. missing token)."""
        import os
        import re
        out: Dict[str, str] = {}
        pattern = re.compile(r"\$\{(\w+)\}")

        def resolve(val: str) -> str:
            return pattern.sub(lambda m: os.environ.get(m.group(1), ""), val)

        for k, v in headers.items():
            s = resolve(str(v)).strip()
            # Skip Authorization (and similar) when value is empty or just "Bearer "
            if not s or (k.lower() == "authorization" and s.lower() == "bearer"):
                continue
            out[k] = s
        if "User-Agent" not in out:
            out["User-Agent"] = DEFAULT_USER_AGENT
        return out

    @retry(
        retry=retry_if_exception_type((aiohttp.ClientError, OSError, ConnectionError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        reraise=True,
    )
    async def fetch(self, source: "Source") -> List[Dict[str, Any]]:
        """GET URL with params/headers and normalize response to items."""
        url = self.url or source.config.get("url", "")
        if not url:
            return []
        params = self.params or source.config.get("params") or {}
        headers = self.headers or self._resolve_headers(source.config.get("headers") or {})

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, headers=headers) as resp:
                    if resp.status in (401, 403):
                        logger.warning(
                            "Source %s returned %s (auth/rate limit). Set token in .env if required.",
                            source.id, resp.status,
                        )
                        return []
                    resp.raise_for_status()
                    # arXiv API returns Atom XML
                    if "arxiv" in url.lower():
                        text = await resp.text()
                        return await self._fetch_arxiv_atom(text, source)
                    data = await resp.json()
            return self._normalize_response(data, source)
        except aiohttp.ClientResponseError as e:
            if e.status in (401, 403):
                logger.warning("Source %s: %s. Add token to .env if needed.", source.id, e)
                return []
            raise

    async def _fetch_arxiv_atom(self, xml_text: str, source: "Source") -> List[Dict[str, Any]]:
        """Parse arXiv Atom XML and return raw items."""
        import asyncio
        import feedparser
        loop = asyncio.get_event_loop()
        def _parse() -> List[Dict[str, Any]]:
            feed = feedparser.parse(xml_text)
            items: List[Dict[str, Any]] = []
            for entry in getattr(feed, "entries", []):
                link = getattr(entry, "link", None)
                if not link:
                    continue
                title = getattr(entry, "title", "Untitled")
                summary = getattr(entry, "summary", "") or ""
                published = getattr(entry, "published", None) or getattr(entry, "updated", None)
                author = None
                if getattr(entry, "authors", []):
                    author = getattr(entry.authors[0], "name", None)
                items.append({
                    "url": link,
                    "title": title,
                    "content": summary,
                    "author": author,
                    "published_at": published,
                    "metadata": {},
                    "external_id": getattr(entry, "id", None) or link,
                })
            return items
        return await loop.run_in_executor(None, _parse)

    def _normalize_response(self, data: Any, source: "Source") -> List[Dict[str, Any]]:
        """Map API-specific response to list of raw item dicts. Override per API shape."""
        source_id = source.id
        # HN Algolia
        if "hits" in data and isinstance(data["hits"], list):
            return self._normalize_hn_algolia(data["hits"], source_id)
        # GitHub search repos
        if "items" in data and isinstance(data["items"], list):
            items = data["items"]
            if items and "html_url" in (items[0] or {}):
                return self._normalize_github_repos(items, source_id)
        # arXiv API (XML is parsed as dict in some clients; here we assume JSON-like)
        if "feed" in data and "entry" in data["feed"]:
            return self._normalize_arxiv(data["feed"]["entry"], source_id)
        # Qiita API v2 (list of items)
        if isinstance(data, list) and data and isinstance(data[0], dict):
            if "url" in data[0] and "title" in data[0]:
                return self._normalize_qiita(data, source_id)
        return []

    def _normalize_hn_algolia(self, hits: List[Dict], source_id: str) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for h in hits:
            url = h.get("url") or h.get("objectID") and f"https://news.ycombinator.com/item?id={h['objectID']}"
            if not url:
                continue
            out.append({
                "url": url,
                "title": h.get("title", "Untitled"),
                "content": h.get("story_text") or h.get("content") or "",
                "author": h.get("author"),
                "published_at": h.get("created_at"),
                "metadata": {"points": h.get("points", 0)},
                "external_id": h.get("objectID"),
            })
        return out

    def _normalize_github_repos(self, items: List[Dict], source_id: str) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for r in items:
            url = r.get("html_url")
            if not url:
                continue
            out.append({
                "url": url,
                "title": r.get("full_name") or r.get("name", "Untitled"),
                "content": r.get("description") or "",
                "author": r.get("owner", {}).get("login") if isinstance(r.get("owner"), dict) else None,
                "published_at": r.get("created_at"),
                "metadata": {"stars": r.get("stargazers_count", 0)},
                "external_id": str(r.get("id", "")),
            })
        return out

    def _normalize_arxiv(self, entries: Any, source_id: str) -> List[Dict[str, Any]]:
        if not isinstance(entries, list):
            entries = [entries] if entries else []
        out: List[Dict[str, Any]] = []
        for e in entries:
            link = None
            if isinstance(e.get("link"), list):
                for l in e["link"]:
                    if isinstance(l, dict) and l.get("href"):
                        link = l["href"]
                        break
            elif isinstance(e.get("link"), dict):
                link = e["link"].get("href")
            else:
                link = e.get("id")
            if not link:
                continue
            title = e.get("title", "Untitled")
            if isinstance(title, dict):
                title = title.get("#text") or title.get("__text__") or "Untitled"
            summary = e.get("summary", "") or ""
            if isinstance(summary, dict):
                summary = summary.get("#text") or summary.get("__text__") or ""
            published = e.get("published") or e.get("updated")
            authors = e.get("author", [])
            if not isinstance(authors, list):
                authors = [authors]
            author = authors[0].get("name") if authors and isinstance(authors[0], dict) else None
            out.append({
                "url": link,
                "title": title,
                "content": summary,
                "author": author,
                "published_at": published,
                "metadata": {},
                "external_id": e.get("id") or link,
            })
        return out

    def _normalize_qiita(self, items: List[Dict], source_id: str) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for it in items:
            url = it.get("url")
            if not url:
                continue
            out.append({
                "url": url,
                "title": it.get("title", "Untitled"),
                "content": it.get("body", "")[:5000] if it.get("body") else "",
                "author": it.get("user", {}).get("id") if isinstance(it.get("user"), dict) else None,
                "published_at": it.get("created_at"),
                "metadata": {"likes_count": it.get("likes_count", 0)},
                "external_id": it.get("id"),
            })
        return out
