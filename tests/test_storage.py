"""Tests for the storage layer: schema, database manager, models, migrations."""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from backend.storage.db import DatabaseManager
from backend.storage.models import Digest, IngestResult, IngestSummary, Item, Metric, Source
from backend.storage.migrations import apply_migrations, get_current_version, reset_database


# --- Fixtures ---

@pytest.fixture
def tmp_db(tmp_path):
    """Return a path to a temporary database file."""
    return str(tmp_path / "test.db")


@pytest.fixture
async def db(tmp_db):
    """Return an initialized DatabaseManager."""
    manager = DatabaseManager(tmp_db)
    await manager.initialize()
    yield manager
    await manager.close()


def make_item(
    source_id: str = "test_source",
    url: str = "https://example.com/article-1",
    title: str = "Test Article",
    category: str = "news",
    language: str = "en",
    content: str = "This is test content about AI and LLMs.",
    published_at: datetime = None,
) -> Item:
    """Create a test Item."""
    if published_at is None:
        published_at = datetime.utcnow()
    canonical = Item.canonicalize_url(url)
    item_id = Item.make_id(url, source_id)
    return Item(
        id=item_id,
        source_id=source_id,
        url=url,
        url_canonical=canonical,
        title=title,
        category=category,
        language=language,
        content=content,
        published_at=published_at,
        ingested_at=datetime.utcnow(),
    )


def make_source(source_id: str = "test_source") -> Source:
    """Create a test Source."""
    return Source(
        id=source_id,
        config={"id": source_id, "type": "rss", "url": "https://example.com/feed"},
    )


# --- Schema & Migration Tests ---

class TestMigrations:
    def test_apply_migrations_creates_tables(self, tmp_db):
        version = apply_migrations(tmp_db)
        assert version >= 1

        conn = sqlite3.connect(tmp_db)
        tables = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        conn.close()

        assert "sources" in tables
        assert "items" in tables
        assert "metrics" in tables
        assert "digests" in tables
        assert "schema_version" in tables
        assert "items_fts" in tables

    def test_idempotent_migrations(self, tmp_db):
        v1 = apply_migrations(tmp_db)
        v2 = apply_migrations(tmp_db)
        assert v1 == v2

    def test_get_current_version(self, tmp_db):
        apply_migrations(tmp_db)
        conn = sqlite3.connect(tmp_db)
        version = get_current_version(conn)
        conn.close()
        assert version >= 1

    def test_reset_database(self, tmp_db):
        apply_migrations(tmp_db)
        # Insert some data
        conn = sqlite3.connect(tmp_db)
        conn.execute(
            "INSERT INTO sources (id, config) VALUES (?, ?)",
            ("test", '{"id": "test"}'),
        )
        conn.commit()
        conn.close()

        reset_database(tmp_db)

        conn = sqlite3.connect(tmp_db)
        count = conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
        conn.close()
        assert count == 0

    def test_wal_mode_enabled(self, tmp_db):
        apply_migrations(tmp_db)
        conn = sqlite3.connect(tmp_db)
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        conn.close()
        assert mode == "wal"


# --- Model Tests ---

class TestModels:
    def test_item_make_id_deterministic(self):
        id1 = Item.make_id("https://example.com/a", "src1")
        id2 = Item.make_id("https://example.com/a", "src1")
        id3 = Item.make_id("https://example.com/b", "src1")
        assert id1 == id2
        assert id1 != id3

    def test_item_canonicalize_url(self):
        assert Item.canonicalize_url("https://www.example.com/path/") == "https://example.com/path"
        assert Item.canonicalize_url("http://example.com/path#frag") == "https://example.com/path"
        assert Item.canonicalize_url("https://example.com") == "https://example.com/"

    def test_item_roundtrip(self):
        item = make_item()
        row = item.to_row()
        assert len(row) == 14

    def test_source_from_config(self):
        cfg = {"id": "test", "type": "rss", "url": "https://example.com/feed"}
        source = Source.from_config(cfg)
        assert source.id == "test"
        assert source.config == cfg
        assert source.enabled is True

    def test_ingest_summary(self):
        summary = IngestSummary()
        summary.add(IngestResult(source_id="a", fetched=10, inserted=8, duplicates=2))
        summary.add(IngestResult(source_id="b", fetched=5, inserted=3, duplicates=1, errors=1))
        assert summary.total_fetched == 15
        assert summary.total_inserted == 11
        assert summary.total_duplicates == 3
        assert summary.total_errors == 1


# --- Database Manager Tests ---

class TestDatabaseManager:
    @pytest.mark.asyncio
    async def test_initialize(self, db):
        assert db._conn is not None

    @pytest.mark.asyncio
    async def test_upsert_and_get_source(self, db):
        source = make_source()
        await db.upsert_source(source)

        retrieved = await db.get_source("test_source")
        assert retrieved is not None
        assert retrieved.id == "test_source"
        assert retrieved.enabled is True

    @pytest.mark.asyncio
    async def test_get_enabled_sources(self, db):
        await db.upsert_source(make_source("src1"))
        await db.upsert_source(make_source("src2"))

        sources = await db.get_enabled_sources()
        assert len(sources) == 2

    @pytest.mark.asyncio
    async def test_update_source_status(self, db):
        await db.upsert_source(make_source())
        now = datetime.utcnow()
        await db.update_source_status("test_source", last_fetch_at=now)

        source = await db.get_source("test_source")
        assert source is not None
        assert source.last_fetch_at is not None

    @pytest.mark.asyncio
    async def test_update_source_error(self, db):
        await db.upsert_source(make_source())
        await db.update_source_status(
            "test_source", last_error="timeout", increment_errors=True
        )

        source = await db.get_source("test_source")
        assert source is not None
        assert source.last_error == "timeout"
        assert source.error_count == 1

    @pytest.mark.asyncio
    async def test_batch_insert_items(self, db):
        await db.upsert_source(make_source())

        items = [
            make_item(url=f"https://example.com/article-{i}", title=f"Article {i}")
            for i in range(100)
        ]
        inserted = await db.batch_insert_items(items)
        assert inserted == 100

        count = await db.count_items()
        assert count == 100

    @pytest.mark.asyncio
    async def test_batch_insert_ignores_duplicates(self, db):
        await db.upsert_source(make_source())

        items = [make_item()]
        await db.batch_insert_items(items)
        inserted = await db.batch_insert_items(items)
        assert inserted == 0

        count = await db.count_items()
        assert count == 1

    @pytest.mark.asyncio
    async def test_get_item(self, db):
        await db.upsert_source(make_source())
        item = make_item()
        await db.batch_insert_items([item])

        retrieved = await db.get_item(item.id)
        assert retrieved is not None
        assert retrieved.title == "Test Article"

    @pytest.mark.asyncio
    async def test_get_items_by_source(self, db):
        await db.upsert_source(make_source())
        items = [
            make_item(url=f"https://example.com/a-{i}") for i in range(5)
        ]
        await db.batch_insert_items(items)

        result = await db.get_items_by_source("test_source")
        assert len(result) == 5

    @pytest.mark.asyncio
    async def test_get_items_by_category(self, db):
        await db.upsert_source(make_source())
        items = [
            make_item(url="https://example.com/news-1", category="news"),
            make_item(url="https://example.com/tips-1", category="tips"),
            make_item(url="https://example.com/paper-1", category="paper"),
        ]
        await db.batch_insert_items(items)

        news = await db.get_items_by_category("news")
        assert len(news) == 1

    @pytest.mark.asyncio
    async def test_item_exists(self, db):
        await db.upsert_source(make_source())
        item = make_item()
        assert not await db.item_exists(item.id)
        await db.batch_insert_items([item])
        assert await db.item_exists(item.id)

    @pytest.mark.asyncio
    async def test_url_canonical_exists(self, db):
        await db.upsert_source(make_source())
        item = make_item()
        assert not await db.url_canonical_exists(item.url_canonical)
        await db.batch_insert_items([item])
        assert await db.url_canonical_exists(item.url_canonical)


# --- FTS Search Tests ---

class TestSearch:
    @pytest.mark.asyncio
    async def test_basic_search(self, db):
        await db.upsert_source(make_source())
        items = [
            make_item(
                url="https://example.com/llm-article",
                title="Introduction to Large Language Models",
                content="LLMs are transforming the field of natural language processing.",
            ),
            make_item(
                url="https://example.com/rag-article",
                title="RAG: Retrieval Augmented Generation",
                content="RAG combines retrieval with generation for better accuracy.",
            ),
            make_item(
                url="https://example.com/unrelated",
                title="Cooking Recipes",
                content="How to make pasta carbonara.",
            ),
        ]
        await db.batch_insert_items(items)

        results = await db.search("language models")
        assert len(results) >= 1
        assert any("Language" in r.title for r in results)

    @pytest.mark.asyncio
    async def test_search_with_category_filter(self, db):
        await db.upsert_source(make_source())
        items = [
            make_item(
                url="https://example.com/news-llm",
                title="LLM News",
                category="news",
                content="News about LLMs",
            ),
            make_item(
                url="https://example.com/tips-llm",
                title="LLM Tips",
                category="tips",
                content="Tips about LLMs",
            ),
        ]
        await db.batch_insert_items(items)

        results = await db.search("LLM", category="news")
        assert len(results) == 1
        assert results[0].category == "news"

    @pytest.mark.asyncio
    async def test_search_with_language_filter(self, db):
        await db.upsert_source(make_source())
        items = [
            make_item(
                url="https://example.com/en-article",
                title="English AI Article",
                language="en",
                content="AI content in English",
            ),
            make_item(
                url="https://example.com/ja-article",
                title="日本語AI記事",
                language="ja",
                content="AI content in Japanese",
            ),
        ]
        await db.batch_insert_items(items)

        results = await db.search("AI", language="en")
        assert len(results) == 1
        assert results[0].language == "en"

    @pytest.mark.asyncio
    async def test_search_count(self, db):
        await db.upsert_source(make_source())
        items = [
            make_item(
                url=f"https://example.com/ai-{i}",
                title=f"AI Article {i}",
                content="Artificial intelligence content",
            )
            for i in range(10)
        ]
        await db.batch_insert_items(items)

        count = await db.search_count("artificial intelligence")
        assert count == 10

    @pytest.mark.asyncio
    async def test_search_japanese(self, db):
        """Test FTS with Japanese content (unicode61 tokenizer handles CJK)."""
        await db.upsert_source(make_source())
        items = [
            make_item(
                url="https://example.com/ja-1",
                title="大規模言語モデルの最新動向",
                language="ja",
                content="LLMの技術革新について解説します",
            ),
        ]
        await db.batch_insert_items(items)

        results = await db.search("LLM")
        assert len(results) >= 1


# --- Performance Tests ---

class TestPerformance:
    @pytest.mark.asyncio
    async def test_batch_insert_10k(self, db):
        """10K items should insert in under 5 seconds."""
        await db.upsert_source(make_source())
        items = [
            make_item(
                url=f"https://example.com/perf-{i}",
                title=f"Performance Test Article {i}",
                content=f"Content for performance test article number {i} about AI topics.",
            )
            for i in range(10_000)
        ]

        t0 = time.monotonic()
        inserted = await db.batch_insert_items(items)
        elapsed = time.monotonic() - t0

        assert inserted == 10_000
        assert elapsed < 5.0, f"Batch insert took {elapsed:.2f}s (limit: 5s)"

    @pytest.mark.asyncio
    async def test_search_speed_10k(self, db):
        """FTS search on 10K items should be under 1 second."""
        await db.upsert_source(make_source())
        items = [
            make_item(
                url=f"https://example.com/search-perf-{i}",
                title=f"Article about AI agents and RAG systems {i}",
                content=f"Content {i}: Large language models are used for retrieval augmented generation.",
            )
            for i in range(10_000)
        ]
        await db.batch_insert_items(items)

        t0 = time.monotonic()
        results = await db.search("language models RAG")
        elapsed = time.monotonic() - t0

        assert len(results) > 0
        assert elapsed < 1.0, f"Search took {elapsed:.2f}s (limit: 1s)"


# --- Metrics Tests ---

class TestMetrics:
    @pytest.mark.asyncio
    async def test_upsert_metrics(self, db):
        await db.upsert_source(make_source())
        item = make_item()
        await db.batch_insert_items([item])

        metric = Metric(
            item_id=item.id,
            score=0.85,
            score_authority=0.9,
            score_recency=0.8,
        )
        count = await db.upsert_metrics([metric])
        assert count == 1

    @pytest.mark.asyncio
    async def test_get_top_items(self, db):
        await db.upsert_source(make_source())
        items = [
            make_item(url=f"https://example.com/top-{i}", title=f"Top {i}")
            for i in range(5)
        ]
        await db.batch_insert_items(items)

        metrics = [
            Metric(item_id=item.id, score=0.5 + i * 0.1)
            for i, item in enumerate(items)
        ]
        await db.upsert_metrics(metrics)

        top = await db.get_top_items(limit=3)
        assert len(top) == 3
        # Should be ordered by score DESC
        assert top[0][1].score >= top[1][1].score


# --- Digest Tests ---

class TestDigests:
    @pytest.mark.asyncio
    async def test_save_and_get_digest(self, db):
        digest = Digest(
            id=None,
            date="2025-01-15",
            section="news",
            content_markdown="# Daily News\n\n- Article 1\n- Article 2",
            content_json={"items": [{"title": "Article 1"}, {"title": "Article 2"}]},
        )
        digest_id = await db.save_digest(digest)
        assert digest_id > 0

        result = await db.get_digest("2025-01-15", "news")
        assert len(result) == 1
        assert result[0].section == "news"
        assert "Daily News" in result[0].content_markdown

    @pytest.mark.asyncio
    async def test_digest_upsert(self, db):
        """Saving same date+section should update, not duplicate."""
        digest1 = Digest(
            id=None, date="2025-01-15", section="news",
            content_markdown="v1", content_json={},
        )
        digest2 = Digest(
            id=None, date="2025-01-15", section="news",
            content_markdown="v2", content_json={},
        )
        await db.save_digest(digest1)
        await db.save_digest(digest2)

        result = await db.get_digest("2025-01-15", "news")
        assert len(result) == 1
        assert result[0].content_markdown == "v2"


# --- Maintenance Tests ---

class TestMaintenance:
    @pytest.mark.asyncio
    async def test_vacuum(self, db):
        await db.vacuum()  # Should not raise

    @pytest.mark.asyncio
    async def test_optimize_fts(self, db):
        await db.optimize_fts()  # Should not raise

    @pytest.mark.asyncio
    async def test_integrity_check(self, db):
        result = await db.integrity_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_get_stats(self, db):
        stats = await db.get_stats()
        assert "total_items" in stats
        assert "total_sources" in stats
        assert stats["total_items"] == 0
