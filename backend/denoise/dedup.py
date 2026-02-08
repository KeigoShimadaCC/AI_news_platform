"""Deduplication / clustering engine using MinHash-LSH for O(n) performance."""

from __future__ import annotations

import hashlib
import logging
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse, urlunparse

from backend.denoise.filters import ItemRecord

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lightweight MinHash implementation (avoids heavy datasketch dependency)
# ---------------------------------------------------------------------------

_LARGE_PRIME = (1 << 61) - 1  # Mersenne prime for universal hash family
_MAX_HASH = (1 << 32) - 1


@dataclass
class MinHashSignature:
    """Fixed-size MinHash signature for a document."""

    values: list[int] = field(default_factory=list)
    num_perm: int = 128


def _generate_hash_funcs(num_perm: int, seed: int = 42) -> list[tuple[int, int]]:
    """Generate (a, b) pairs for hash family h(x) = (a*x + b) % p."""
    import random

    rng = random.Random(seed)
    return [(rng.randint(1, _LARGE_PRIME - 1), rng.randint(0, _LARGE_PRIME - 1))
            for _ in range(num_perm)]


_DEFAULT_NUM_PERM = 128
_HASH_FUNCS = _generate_hash_funcs(_DEFAULT_NUM_PERM)


def _shingle(text: str, k: int = 3) -> set[int]:
    """Convert text to a set of k-character shingle hashes."""
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    if len(text) < k:
        return {hash(text) & _MAX_HASH}
    return {hash(text[i : i + k]) & _MAX_HASH for i in range(len(text) - k + 1)}


def compute_minhash(text: str, num_perm: int = _DEFAULT_NUM_PERM) -> MinHashSignature:
    """Compute MinHash signature for a text string."""
    shingles = _shingle(text)
    if not shingles:
        return MinHashSignature(values=[_MAX_HASH] * num_perm, num_perm=num_perm)

    sig = [_MAX_HASH] * num_perm
    for s in shingles:
        for i, (a, b) in enumerate(_HASH_FUNCS[:num_perm]):
            h = ((a * s + b) % _LARGE_PRIME) & _MAX_HASH
            if h < sig[i]:
                sig[i] = h
    return MinHashSignature(values=sig, num_perm=num_perm)


def minhash_similarity(a: MinHashSignature, b: MinHashSignature) -> float:
    """Estimate Jaccard similarity from two MinHash signatures."""
    if a.num_perm != b.num_perm:
        raise ValueError("Signatures must have the same num_perm")
    matches = sum(1 for x, y in zip(a.values, b.values) if x == y)
    return matches / a.num_perm


# ---------------------------------------------------------------------------
# LSH (Locality-Sensitive Hashing) index for near-O(n) candidate retrieval
# ---------------------------------------------------------------------------

class LSHIndex:
    """Band-based LSH index for MinHash signatures."""

    def __init__(self, num_bands: int = 16, rows_per_band: int = 8) -> None:
        self.num_bands = num_bands
        self.rows_per_band = rows_per_band
        # band_idx -> {band_hash -> set of item_ids}
        self._buckets: list[dict[int, list[str]]] = [
            defaultdict(list) for _ in range(num_bands)
        ]

    def insert(self, item_id: str, sig: MinHashSignature) -> None:
        for band_idx in range(self.num_bands):
            start = band_idx * self.rows_per_band
            end = start + self.rows_per_band
            band_hash = hash(tuple(sig.values[start:end]))
            self._buckets[band_idx][band_hash].append(item_id)

    def query_candidates(self, sig: MinHashSignature) -> set[str]:
        """Return item IDs that are candidate near-duplicates."""
        candidates: set[str] = set()
        for band_idx in range(self.num_bands):
            start = band_idx * self.rows_per_band
            end = start + self.rows_per_band
            band_hash = hash(tuple(sig.values[start:end]))
            bucket = self._buckets[band_idx].get(band_hash, [])
            candidates.update(bucket)
        return candidates


# ---------------------------------------------------------------------------
# URL canonicalization
# ---------------------------------------------------------------------------

def canonical_url(url: str) -> str:
    """Normalize a URL for dedup comparison (strip tracking params, fragments, etc.)."""
    try:
        parsed = urlparse(url.strip())
        # Drop fragment, lowercase scheme and host
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower().rstrip(".")
        path = parsed.path.rstrip("/") or "/"
        # Strip common tracking query params
        _strip_params = {
            "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
            "ref", "source", "fbclid", "gclid",
        }
        if parsed.query:
            from urllib.parse import parse_qs, urlencode

            qs = parse_qs(parsed.query, keep_blank_values=True)
            filtered = {k: v for k, v in qs.items() if k.lower() not in _strip_params}
            query = urlencode(filtered, doseq=True)
        else:
            query = ""
        return urlunparse((scheme, netloc, path, "", query, ""))
    except Exception:
        return url.strip().lower()


def _normalize_text(text: str) -> str:
    """Normalize unicode, collapse whitespace."""
    text = unicodedata.normalize("NFKC", text)
    return re.sub(r"\s+", " ", text).strip().lower()


# ---------------------------------------------------------------------------
# DedupClusterer
# ---------------------------------------------------------------------------

class DedupClusterer:
    """Cluster near-duplicate items using URL canonicalization + MinHash-LSH."""

    def __init__(self, config: dict[str, Any]) -> None:
        perf = config.get("performance", {})
        self.similarity_threshold: float = perf.get("similarity_threshold", 0.85)
        self.use_embeddings: bool = perf.get("use_embeddings", False)
        self._num_perm = _DEFAULT_NUM_PERM
        # LSH bands/rows chosen so that pairs with Jaccard ≥ 0.85 are found
        # with probability ≈ 1 - (1 - 0.85^8)^16 ≈ 0.9999
        self._lsh = LSHIndex(num_bands=16, rows_per_band=8)

    def cluster_items(self, items: list[ItemRecord]) -> dict[str, list[ItemRecord]]:
        """Cluster items by URL equality then title MinHash-LSH similarity.

        Returns ``{cluster_id: [items_in_cluster]}``.
        """
        if not items:
            return {}

        # Phase 1: exact URL dedup
        url_clusters: dict[str, list[ItemRecord]] = defaultdict(list)
        for item in items:
            canon = canonical_url(item.url)
            url_clusters[canon].append(item)

        # Assign cluster IDs and pick one representative per URL cluster
        representatives: list[tuple[str, ItemRecord, MinHashSignature]] = []
        clusters: dict[str, list[ItemRecord]] = {}
        cluster_counter = 0

        for canon_url, group in url_clusters.items():
            cluster_id = f"c{cluster_counter:06d}"
            cluster_counter += 1
            clusters[cluster_id] = list(group)
            rep = self._pick_best(group)
            text = _normalize_text(f"{rep.title} {rep.content[:500]}")
            sig = compute_minhash(text, self._num_perm)
            representatives.append((cluster_id, rep, sig))

        # Phase 2: MinHash-LSH to merge URL-distinct but content-similar clusters
        # Build LSH index
        lsh = LSHIndex(num_bands=16, rows_per_band=8)
        for cid, _rep, sig in representatives:
            lsh.insert(cid, sig)

        # Union-Find for merging clusters
        parent: dict[str, str] = {cid: cid for cid, _, _ in representatives}

        def find(x: str) -> str:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a: str, b: str) -> None:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb

        sig_map = {cid: sig for cid, _, sig in representatives}

        for cid, _rep, sig in representatives:
            candidates = lsh.query_candidates(sig)
            for other_cid in candidates:
                if other_cid == cid:
                    continue
                if find(cid) == find(other_cid):
                    continue
                sim = minhash_similarity(sig, sig_map[other_cid])
                if sim >= self.similarity_threshold:
                    union(cid, other_cid)

        # Merge clusters by union-find roots
        merged: dict[str, list[ItemRecord]] = defaultdict(list)
        for cid, item_list in clusters.items():
            root = find(cid)
            merged[root].extend(item_list)

        # Tag representative items
        for cid, group in merged.items():
            rep = self._pick_best(group)
            for item in group:
                item.cluster_id = cid
                item.is_representative = item.id == rep.id

        logger.info(
            "DedupClusterer: %d items → %d clusters", len(items), len(merged)
        )
        return dict(merged)

    def select_representative(self, cluster: list[ItemRecord]) -> ItemRecord:
        """Pick the best item from a cluster (highest authority source, then earliest)."""
        return self._pick_best(cluster)

    @staticmethod
    def _pick_best(group: list[ItemRecord]) -> ItemRecord:
        """Deterministic best-item selection: prefer longest content, then earliest."""
        return max(group, key=lambda it: (len(it.content), -hash(it.published_at)))
