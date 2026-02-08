#!/usr/bin/env python3
"""Quick test: call local Ollama summarizer with one fake item. Run from project root."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Ensure project root is on path
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))

import yaml
from backend.denoise.filters import ItemRecord
from backend.digest.summarizer import LLMSummarizer


def main() -> None:
    config_path = root / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if config.get("llm", {}).get("provider") != "local":
        print("Config llm.provider is not 'local'. Set it to 'local' to test Ollama.", file=sys.stderr)
        sys.exit(1)

    item = ItemRecord(
        id="test-ollama-1",
        source_id="test",
        url="https://example.com/test",
        title="Ollama local test article",
        content="This is a short test to verify the local Ollama summarizer works.",
        author=None,
        published_at="2025-01-01T00:00:00Z",
        fetched_at="2025-01-01T00:00:00Z",
        lang="en",
        category="news",
    )

    summarizer = LLMSummarizer(config)
    result = asyncio.run(summarizer.summarize([item]))
    summary = result.get(item.id, "")

    print("Summary:", summary)
    if not summary:
        sys.exit(1)
    print("OK: Ollama local summarizer works.")


if __name__ == "__main__":
    main()
