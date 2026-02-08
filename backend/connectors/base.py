"""Base connector interface for the AI News Platform."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, List

if TYPE_CHECKING:
    from backend.storage.models import Source


class BaseConnector(ABC):
    """Abstract base for source connectors.

    Subclasses must implement fetch() to return a list of raw item dicts
    with keys: url (required), title, content, author, published_at, metadata, external_id.
    """

    @abstractmethod
    async def fetch(self, source: "Source") -> List[Dict[str, Any]]:
        """Fetch raw items from the source.

        Returns:
            List of dicts with at least: url, title; optional: content, author,
            published_at (ISO or datetime), metadata (e.g. points, score, stars),
            external_id.
        """
        ...
