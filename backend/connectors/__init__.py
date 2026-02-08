"""Source connectors for the AI News Platform.

Supported types: rss, api, rss_or_scrape (RSS with scrape fallback).
"""

from backend.connectors.base import BaseConnector
from backend.connectors.factory import build_connector
from backend.connectors.rss import RSSConnector
from backend.connectors.api import APIConnector
from backend.connectors.scrape_fallback import ScrapeFallbackConnector
from backend.connectors.rss_or_scrape import RSSOrScrapeConnector

__all__ = [
    "BaseConnector",
    "build_connector",
    "RSSConnector",
    "APIConnector",
    "ScrapeFallbackConnector",
    "RSSOrScrapeConnector",
]
