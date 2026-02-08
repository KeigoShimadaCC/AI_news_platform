"""Tests for the ingestion pipeline orchestrator and CLI."""

from __future__ import annotations

import asyncio
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from backend.pipeline.orchestrator import IngestOrchestrator, SnapshotManager
from backend.storage.db import DatabaseManager
from backend.storage.models import IngestResult, Item, Source


# --- Fixtures ---

@pytest.fixture
def tmp_dir(tmp_path):
    """Return a temporary directory with config and data subdirs."""
    # Create config
    config = {
        "sources": [
            {
                "id": "test_rss",
                "type": "rss",
                "url": "https://example.com/feed.xml",
                "category": "news",
                "authority": 0.8,
                "refresh_hours": 6,
                "lang": "en",
            },
            {
                "id": "test_api",
                "type": "api",
                "url": "https://example.com/api",
                "category": "tips",
                "authority": 0.7,
                "refresh_hours": 12,
                "lang": "ja",
            },
        ],
        "performance": {
            "max_concurrent_sources": 5,
            "request_timeout_seconds": 10,
        },
    }
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump(config))

    db_path = tmp_path / "data" / "test.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    snapshot_dir = tmp_path / "data" / "snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    return {
        "config_path": str(config_path),
        "db_path": str(db_path),
        "snapshot_dir": str(snapshot_dir),
        "tmp_path": tmp_path,
    }


def make_raw_items(count: int = 5, source_id: str = "test_rss") -> List[Dict[str, Any]]:
    """Create raw item dicts as a connector would return."""
    return [
        {
            "url": f"https://example.com/article-{i}",
            "title": f"Test Article {i}",
            "content": f"Content for article {i} about AI and machine learning.",
            "author": "Test Author",
            "published_at": datetime.utcnow().isoformat(),
            "metadata": {"score": i * 10},
        }
        for i in range(count)
    ]


class MockConnector:
    """Mock connector that returns pre-configured items."""

    def __init__(self, items: List[Dict[str, Any]]):
        self._items = items

    async def fetch(self, source: Source) -> List[Dict[str, Any]]:
        return self._items


class FailingConnector:
    """Mock connector that raises an exception."""

    async def fetch(self, source: Source) -> List[Dict[str, Any]]:
        raise ConnectionError("Simulated network failure")


# --- Snapshot Manager Tests ---

class TestSnapshotManager:
    def test_save_snapshot(self, tmp_path):
        mgr = SnapshotManager(str(tmp_path / "snapshots"))
        path = mgr.save("test_source", "https://example.com/article", "<html>content</html>")
        assert Path(path).exists()
        assert Path(path).read_text() == "<html>content</html>"

    def test_snapshot_exists(self, tmp_path):
        mgr = SnapshotManager(str(tmp_path / "snapshots"))
        assert not mgr.exists("test_source", "https://example.com/article")
        mgr.save("test_source", "https://example.com/article", "<html>test</html>")
        assert mgr.exists("test_source", "https://example.com/article")

    def test_snapshot_directory_structure(self, tmp_path):
        mgr = SnapshotManager(str(tmp_path / "snapshots"))
        mgr.save("my_source", "https://example.com/page", "<html/>")

        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        expected_dir = tmp_path / "snapshots" / "my_source" / date_str
        assert expected_dir.exists()
        files = list(expected_dir.iterdir())
        assert len(files) == 1
        assert files[0].suffix == ".html"


# --- Orchestrator Tests ---

class TestIngestOrchestrator:
    @pytest.mark.asyncio
    async def test_ingest_all_with_mock_connector(self, tmp_dir):
        raw_items = make_raw_items(5, "test_rss")
        mock_factory = lambda cfg: MockConnector(raw_items)

        orchestrator = IngestOrchestrator(
            config_path=tmp_dir["config_path"],
            db_path=tmp_dir["db_path"],
            snapshot_dir=tmp_dir["snapshot_dir"],
            connector_factory=mock_factory,
        )
        await orchestrator.initialize()
        try:
            summary = await orchestrator.ingest_all()
            assert summary.total_fetched == 10  # 5 items * 2 sources
            assert summary.total_inserted > 0
            assert summary.total_errors == 0
        finally:
            await orchestrator.close()

    @pytest.mark.asyncio
    async def test_ingest_single_source(self, tmp_dir):
        raw_items = make_raw_items(3)
        mock_factory = lambda cfg: MockConnector(raw_items)

        orchestrator = IngestOrchestrator(
            config_path=tmp_dir["config_path"],
            db_path=tmp_dir["db_path"],
            snapshot_dir=tmp_dir["snapshot_dir"],
            connector_factory=mock_factory,
        )
        await orchestrator.initialize()
        try:
            summary = await orchestrator.ingest_all(source_ids=["test_rss"])
            assert len(summary.results) == 1
            assert summary.results[0].source_id == "test_rss"
            assert summary.total_fetched == 3
        finally:
            await orchestrator.close()

    @pytest.mark.asyncio
    async def test_ingest_handles_errors(self, tmp_dir):
        mock_factory = lambda cfg: FailingConnector()

        orchestrator = IngestOrchestrator(
            config_path=tmp_dir["config_path"],
            db_path=tmp_dir["db_path"],
            snapshot_dir=tmp_dir["snapshot_dir"],
            connector_factory=mock_factory,
        )
        await orchestrator.initialize()
        try:
            summary = await orchestrator.ingest_all(source_ids=["test_rss"])
            assert summary.total_errors >= 1
            assert summary.results[0].error_message is not None
        finally:
            await orchestrator.close()

    @pytest.mark.asyncio
    async def test_ingest_deduplicates(self, tmp_dir):
        raw_items = make_raw_items(3)
        mock_factory = lambda cfg: MockConnector(raw_items)

        orchestrator = IngestOrchestrator(
            config_path=tmp_dir["config_path"],
            db_path=tmp_dir["db_path"],
            snapshot_dir=tmp_dir["snapshot_dir"],
            connector_factory=mock_factory,
        )
        await orchestrator.initialize()
        try:
            # First ingest
            summary1 = await orchestrator.ingest_all(source_ids=["test_rss"])
            assert summary1.total_inserted == 3

            # Second ingest - should all be duplicates
            summary2 = await orchestrator.ingest_all(source_ids=["test_rss"])
            assert summary2.total_duplicates == 3
            assert summary2.total_inserted == 0
        finally:
            await orchestrator.close()

    @pytest.mark.asyncio
    async def test_ingest_without_connector(self, tmp_dir):
        """Without a connector factory, sources should be skipped gracefully."""
        orchestrator = IngestOrchestrator(
            config_path=tmp_dir["config_path"],
            db_path=tmp_dir["db_path"],
            snapshot_dir=tmp_dir["snapshot_dir"],
            connector_factory=None,
        )
        await orchestrator.initialize()
        try:
            summary = await orchestrator.ingest_all()
            assert summary.total_fetched == 0
            assert summary.total_errors == 0
        finally:
            await orchestrator.close()

    @pytest.mark.asyncio
    async def test_source_status_updated_on_success(self, tmp_dir):
        raw_items = make_raw_items(2)
        mock_factory = lambda cfg: MockConnector(raw_items)

        orchestrator = IngestOrchestrator(
            config_path=tmp_dir["config_path"],
            db_path=tmp_dir["db_path"],
            snapshot_dir=tmp_dir["snapshot_dir"],
            connector_factory=mock_factory,
        )
        await orchestrator.initialize()
        try:
            await orchestrator.ingest_all(source_ids=["test_rss"])
            source = await orchestrator.db.get_source("test_rss")
            assert source is not None
            assert source.last_fetch_at is not None
            assert source.last_error is None
        finally:
            await orchestrator.close()

    @pytest.mark.asyncio
    async def test_source_status_updated_on_error(self, tmp_dir):
        mock_factory = lambda cfg: FailingConnector()

        orchestrator = IngestOrchestrator(
            config_path=tmp_dir["config_path"],
            db_path=tmp_dir["db_path"],
            snapshot_dir=tmp_dir["snapshot_dir"],
            connector_factory=mock_factory,
        )
        await orchestrator.initialize()
        try:
            await orchestrator.ingest_all(source_ids=["test_rss"])
            source = await orchestrator.db.get_source("test_rss")
            assert source is not None
            assert source.last_error is not None
            assert source.error_count == 1
        finally:
            await orchestrator.close()


# --- Normalization Tests ---

class TestNormalization:
    def test_normalize_items(self, tmp_dir):
        orchestrator = IngestOrchestrator(
            config_path=tmp_dir["config_path"],
            db_path=tmp_dir["db_path"],
        )
        source = Source.from_config({
            "id": "test",
            "type": "rss",
            "url": "https://example.com",
            "category": "news",
            "lang": "en",
        })
        raw = [
            {
                "url": "https://www.example.com/article/",
                "title": "Test",
                "published_at": "2025-01-15T10:00:00Z",
            }
        ]

        items = orchestrator._normalize_items(raw, source)
        assert len(items) == 1
        assert items[0].url_canonical == "https://example.com/article"
        assert items[0].category == "news"
        assert items[0].language == "en"

    def test_normalize_skips_empty_urls(self, tmp_dir):
        orchestrator = IngestOrchestrator(
            config_path=tmp_dir["config_path"],
            db_path=tmp_dir["db_path"],
        )
        source = Source.from_config({
            "id": "test", "type": "rss", "url": "https://example.com",
            "category": "news", "lang": "en",
        })
        raw = [{"url": "", "title": "No URL"}]

        items = orchestrator._normalize_items(raw, source)
        assert len(items) == 0


# --- CLI Tests ---

class TestCLI:
    def test_cli_imports(self):
        """Verify CLI module can be imported."""
        from backend.pipeline.cli import cli, main
        assert cli is not None
        assert main is not None

    def test_cli_group_exists(self):
        from backend.pipeline.cli import cli
        assert hasattr(cli, "commands")
