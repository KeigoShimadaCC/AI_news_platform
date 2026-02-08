"""Fetch article page HTML and extract main body text. Used when list API does not include content."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Optional

import aiohttp
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

DEFAULT_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


async def fetch_article_body(
    url: str,
    *,
    user_agent: str = DEFAULT_USER_AGENT,
    timeout: float = 15.0,
) -> Optional[str]:
    """Fetch URL and extract main article body text.

    Tries (1) __NEXT_DATA__ script (Next.js), (2) JSON-LD articleBody,
    (3) <article> or main content area by common class names.
    Returns None on failure or if nothing found.
    """
    headers = {"User-Agent": user_agent}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                if resp.status != 200:
                    return None
                html = await resp.text()
    except Exception as e:
        logger.debug("Failed to fetch %s: %s", url, e)
        return None

    return _extract_body_from_html(html, url)


def _extract_body_from_html(html: str, url: str) -> Optional[str]:
    """Extract main content from HTML. Prefer structured data, then semantic/class-based."""
    # 1) Next.js __NEXT_DATA__
    body = _extract_from_next_data(html)
    if body:
        return _normalize_text(body)

    # 2) JSON-LD articleBody
    body = _extract_from_json_ld(html)
    if body:
        return _normalize_text(body)

    # 3) Semantic HTML / common content selectors
    body = _extract_from_selectors(html, url)
    if body:
        return _normalize_text(body)

    return None


def _extract_from_next_data(html: str) -> Optional[str]:
    """Extract article body from Next.js __NEXT_DATA__ script."""
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*type="application/json"[^>]*>(.*?)</script>', html, re.DOTALL)
    if not m:
        return None
    try:
        data = json.loads(m.group(1))
        # Zenn: props.pageProps.article.body or similar
        props = (data.get("props") or {}).get("pageProps") or {}
        body = props.get("article", {}).get("body")
        if isinstance(body, str) and body.strip():
            return body
        # Some Next apps put content in different paths
        for key in ("body", "content", "markdown", "html"):
            val = props.get(key)
            if isinstance(val, str) and val.strip():
                return val
    except (json.JSONDecodeError, TypeError):
        pass
    return None


def _extract_from_json_ld(html: str) -> Optional[str]:
    """Extract from JSON-LD schema.org Article articleBody."""
    soup = BeautifulSoup(html, "lxml")
    for script in soup.find_all("script", type="application/ld+json"):
        if not script.string:
            continue
        try:
            data = json.loads(script.string)
            if isinstance(data, dict) and data.get("@type") == "Article":
                body = data.get("articleBody")
                if isinstance(body, str) and body.strip():
                    return body
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and item.get("@type") == "Article":
                        body = item.get("articleBody")
                        if isinstance(body, str) and body.strip():
                            return body
        except (json.JSONDecodeError, TypeError):
            continue
    return None


def _extract_from_selectors(html: str, url: str) -> Optional[str]:
    """Extract from semantic/class-based selectors. Zenn and many sites use article or main."""
    soup = BeautifulSoup(html, "lxml")

    # Remove script/style
    for tag in soup.find_all(["script", "style", "nav", "header", "footer"]):
        tag.decompose()

    # Try in order: article, [data-content], main, .article-body, .content, .post
    selectors = [
        "article",
        "[data-content]",
        "main",
        ".ArticleContent",
        ".article-content",
        ".article_body",
        ".post-content",
        ".content",
        ".markdown",
        ".prose",
        "[class*='articleBody']",
        "[class*='article-body']",
    ]
    for sel in selectors:
        el = soup.select_one(sel)
        if el:
            text = el.get_text(separator="\n", strip=True)
            if len(text) > 100:  # likely main content
                return text

    # Fallback: largest paragraph block
    body = soup.find("body")
    if body:
        text = body.get_text(separator="\n", strip=True)
        if len(text) > 200:
            return text
    return None


def _normalize_text(s: str, max_len: int = 100_000) -> str:
    """Collapse whitespace and truncate."""
    s = re.sub(r"\s+", " ", s).strip()
    return s[:max_len] if len(s) > max_len else s
