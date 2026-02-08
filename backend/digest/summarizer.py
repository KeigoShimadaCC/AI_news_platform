"""LLM summarizer with multi-provider support (OpenAI, Anthropic, local, mock)."""

from __future__ import annotations

import asyncio
import hashlib
import logging
from typing import Any

from backend.denoise.filters import ItemRecord

logger = logging.getLogger(__name__)


class LLMSummarizer:
    """Generate "why it matters" summaries using configurable LLM providers."""

    def __init__(self, config: dict[str, Any]) -> None:
        llm = config.get("llm", {})
        self.provider: str = llm.get("provider", "mock")
        self.model: str = llm.get("model", "gpt-4o-mini")
        self.max_tokens: int = llm.get("max_tokens", 150)
        self.temperature: float = llm.get("temperature", 0.7)
        self.concurrent_requests: int = llm.get("concurrent_requests", 10)
        self.cache_summaries: bool = llm.get("cache_summaries", True)
        self.local_url: str = llm.get("local_url", "http://localhost:11434/v1")
        self.local_model: str = llm.get("local_model", "llama3.2")

        # In-memory summary cache (keyed by content hash)
        self._cache: dict[str, str] = {}

    async def summarize(self, items: list[ItemRecord]) -> dict[str, str]:
        """Generate summaries for a list of items.

        Returns ``{item_id: summary_text}``.
        """
        if not items:
            return {}

        # Deduplicate work via content hash
        to_summarize: list[tuple[ItemRecord, str]] = []
        results: dict[str, str] = {}

        for item in items:
            cache_key = self._cache_key(item)
            if self.cache_summaries and cache_key in self._cache:
                results[item.id] = self._cache[cache_key]
            else:
                to_summarize.append((item, cache_key))

        if to_summarize:
            # Process in batches of concurrent_requests
            for i in range(0, len(to_summarize), self.concurrent_requests):
                batch = to_summarize[i : i + self.concurrent_requests]
                tasks = [self._summarize_one(item) for item, _ in batch]
                summaries = await asyncio.gather(*tasks, return_exceptions=True)

                for (item, cache_key), summary in zip(batch, summaries):
                    if isinstance(summary, Exception):
                        logger.warning("Summary failed for %s: %s", item.id, summary)
                        text = self._fallback_summary(item)
                    else:
                        text = summary
                    results[item.id] = text
                    if self.cache_summaries:
                        self._cache[cache_key] = text

        return results

    async def _summarize_one(self, item: ItemRecord) -> str:
        """Dispatch to the configured provider."""
        prompt = self._build_prompt(item)

        if self.provider == "mock":
            return self._mock_summary(item)
        elif self.provider == "openai":
            return await self._call_openai(prompt)
        elif self.provider == "anthropic":
            return await self._call_anthropic(prompt)
        elif self.provider == "local":
            return await self._call_local(prompt)
        else:
            logger.warning("Unknown provider %r, using mock", self.provider)
            return self._mock_summary(item)

    # ------------------------------------------------------------------
    # Provider implementations
    # ------------------------------------------------------------------

    async def _call_openai(self, prompt: str) -> str:
        from openai import AsyncOpenAI

        client = AsyncOpenAI()
        resp = await client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a tech news analyst. Write a concise 1-2 sentence summary explaining why this item matters for AI practitioners."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=self.max_tokens,
            temperature=self.temperature,
        )
        return resp.choices[0].message.content or ""

    async def _call_anthropic(self, prompt: str) -> str:
        from anthropic import AsyncAnthropic

        client = AsyncAnthropic()
        resp = await client.messages.create(
            model=self.model or "claude-haiku-4-5-20251001",
            max_tokens=self.max_tokens,
            system="You are a tech news analyst. Write a concise 1-2 sentence summary explaining why this item matters for AI practitioners.",
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text

    async def _call_local(self, prompt: str) -> str:
        """Call a local Ollama-compatible OpenAI API."""
        from openai import AsyncOpenAI

        client = AsyncOpenAI(base_url=self.local_url, api_key="ollama")
        resp = await client.chat.completions.create(
            model=self.local_model,
            messages=[
                {"role": "system", "content": "You are a tech news analyst. Write a concise 1-2 sentence summary explaining why this item matters for AI practitioners."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=self.max_tokens,
            temperature=self.temperature,
        )
        return resp.choices[0].message.content or ""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_prompt(item: ItemRecord) -> str:
        content_preview = item.content[:800] if item.content else "(no content)"
        return (
            f"Title: {item.title}\n"
            f"Source: {item.source_id}\n"
            f"Category: {item.category}\n"
            f"Content: {content_preview}\n\n"
            f"Summarize why this matters in 1-2 sentences."
        )

    @staticmethod
    def _mock_summary(item: ItemRecord) -> str:
        """Template-based summary for testing (no API calls)."""
        source_label = item.source_id.replace("_", " ").title()
        return f"{item.title} — from {source_label} ({item.category})."

    @staticmethod
    def _fallback_summary(item: ItemRecord) -> str:
        """Fallback when LLM call fails."""
        return item.title[:200]

    @staticmethod
    def _cache_key(item: ItemRecord) -> str:
        raw = f"{item.url}:{item.title}:{item.content[:200]}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]
