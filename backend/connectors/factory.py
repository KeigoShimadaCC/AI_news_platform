"""Connector factory: build the right connector from config.yaml source type."""

from __future__ import annotations

from typing import Any, Dict

from backend.pipeline.orchestrator import Connector
from backend.connectors.rss import RSSConnector
from backend.connectors.api import APIConnector
from backend.connectors.rss_or_scrape import RSSOrScrapeConnector


def build_connector(config: Dict[str, Any]) -> Connector:
    """Return a connector for the given source config.

    config must have 'type' (rss | api | rss_or_scrape) and type-specific fields
    (url, params, headers, etc.).
    """
    source_type = (config.get("type") or "rss").lower().strip()
    if source_type == "rss":
        return RSSConnector(config)
    if source_type == "api":
        return APIConnector(config)
    if source_type == "rss_or_scrape":
        return RSSOrScrapeConnector(config)
    # Default to RSS for unknown types so existing configs keep working
    return RSSConnector(config)
