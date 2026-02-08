# Architecture & Scalability

## Design Principles

1. **Local-First, Cloud-Ready**: Built for local macOS but architected to scale
2. **Config-Driven**: Zero-code source additions via YAML
3. **Pluggable Components**: Swap connectors, rankers, LLMs without core changes
4. **Performance by Default**: Async I/O, batch processing, connection pooling, FTS5
5. **Resilient**: Circuit breakers, retries, per-source isolation

## Scalability Patterns

### 1. Connector Layer (Horizontal Scaling)

**Current (Local)**:
- Async concurrent fetching (10+ sources in parallel)
- Connection pooling per source
- Circuit breaker prevents cascade failures
- Retry with exponential backoff

**Future (Distributed)**:
- Deploy multiple ingest workers
- Message queue (RabbitMQ/SQS) for source assignments
- Distributed rate limiting (Redis)
- Centralized monitoring (Prometheus)

```python
# Scalability built-in:
class ConnectorPool:
    async def fetch_all(self, sources: List[Source]) -> List[Item]:
        # Semaphore limits concurrency
        async with asyncio.Semaphore(config.max_concurrent):
            tasks = [self.fetch_source(s) for s in sources]
            return await asyncio.gather(*tasks, return_exceptions=True)
```

### 2. Storage Layer (Vertical & Read Scaling)

**Current (SQLite)**:
- WAL mode: concurrent readers + single writer
- FTS5 with optimized tokenizers
- Batch inserts (1000 items/txn)
- Prepared statements & query caching

**Scaling Path**:
- **10K items**: Current setup, sub-second search
- **100K items**: Add partitioning, archive old data
- **1M+ items**: Migrate to PostgreSQL or TimescaleDB
- **Read replicas**: SQLite supports streaming replication (Litestream)

```sql
-- Partitioning strategy (future)
CREATE TABLE items_2025_02 AS SELECT * FROM items WHERE created_date BETWEEN ...;
CREATE INDEX idx_items_2025_02_fts ON items_2025_02_fts(title, content);
```

### 3. Denoising & Ranking (CPU Scaling)

**Current (Single Machine)**:
- MinHash/LSH for O(n) deduplication (not O(n²))
- Cached embeddings (disk cache)
- Vectorized NumPy operations
- Optional multiprocessing for CPU-bound tasks

**Scaling Path**:
- **GPU acceleration**: Use CUDA for embedding computation
- **Distributed compute**: Spark/Dask for massive dedup
- **Incremental updates**: Only recompute changed clusters

```python
# Incremental clustering (prevents full recomputation)
class IncrementalClusterer:
    def add_items(self, new_items: List[Item]):
        # Only compute similarity for new vs existing
        # Not new vs new + existing vs existing
```

### 4. API & UI Layer (Request Scaling)

**Current (Next.js)**:
- Server-side rendering (SSR)
- API route caching (in-memory)
- Pagination (50 items/page)
- Debounced search queries

**Scaling Path**:
- **Static generation**: Pre-generate digest pages
- **CDN caching**: Deploy to Vercel Edge
- **Redis cache**: API response caching
- **WebSocket**: Real-time updates (ingest status)

```typescript
// Built-in pagination
export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const page = parseInt(searchParams.get('page') || '1');
  const limit = 50;
  const offset = (page - 1) * limit;
  // ...
}
```

## Performance Benchmarks (Target)

| Operation | Target | Current | Scaling Limit |
|-----------|--------|---------|---------------|
| Ingest 10 sources | <30s | TBD | 50 sources |
| Search 10K items | <1s | TBD | 100K items |
| Deduplicate 1K items | <5s | TBD | 10K items |
| Generate digest | <30s | TBD | 1M items |
| API response (cached) | <100ms | TBD | ∞ (CDN) |

## Monitoring & Observability

### Metrics to Track

1. **Ingest Pipeline**:
   - `source_fetch_duration_seconds{source_id}`
   - `source_fetch_errors_total{source_id, error_type}`
   - `items_ingested_total{source_id, category}`

2. **Storage**:
   - `db_size_bytes`
   - `fts_index_size_bytes`
   - `query_duration_seconds{query_type}`

3. **Dedup/Ranking**:
   - `dedup_clusters_total`
   - `scoring_duration_seconds`
   - `llm_api_calls_total{provider, success}`

4. **API**:
   - `http_request_duration_seconds{endpoint}`
   - `http_requests_total{endpoint, status}`
   - `cache_hit_ratio{endpoint}`

### Implementation

```python
# backend/monitoring/metrics.py
from prometheus_client import Counter, Histogram, Gauge

fetch_duration = Histogram(
    'source_fetch_duration_seconds',
    'Time to fetch from source',
    ['source_id']
)

@fetch_duration.labels(source_id).time()
async def fetch_source(source: Source):
    # ...
```

## Failure Modes & Mitigation

| Failure | Impact | Mitigation |
|---------|--------|-----------|
| Single source fails | Missing items from that source | Circuit breaker, skip source |
| Database locked | Writes blocked | WAL mode, connection pooling |
| LLM API rate limit | Summary generation fails | Exponential backoff, queue |
| FTS index corrupt | Search fails | Auto-rebuild on error |
| Disk full | All writes fail | Monitor disk usage, alert |

## Future: Multi-Machine Deployment

```
┌────────────┐     ┌────────────┐     ┌────────────┐
│  Ingest    │     │  Ingest    │     │  Ingest    │
│  Worker 1  │     │  Worker 2  │     │  Worker N  │
└─────┬──────┘     └─────┬──────┘     └─────┬──────┘
      │                  │                  │
      └──────────────────┼──────────────────┘
                         │
                    ┌────▼─────┐
                    │  Queue   │ (RabbitMQ)
                    └────┬─────┘
                         │
                ┌────────▼─────────┐
                │   PostgreSQL     │ (Primary)
                └────────┬─────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
   ┌────▼─────┐    ┌────▼─────┐    ┌────▼─────┐
   │ Replica  │    │ Replica  │    │ Replica  │
   │    1     │    │    2     │    │    N     │
   └────┬─────┘    └────┬─────┘    └────┬─────┘
        │                │                │
        └────────────────┼────────────────┘
                         │
                    ┌────▼─────┐
                    │   CDN    │ (Vercel/Cloudflare)
                    └──────────┘
```

## Adding Custom Scalability

### Custom Connector with Connection Pooling

```python
class MyAPIConnector(BaseConnector):
    _pool: Optional[aiohttp.ClientSession] = None

    @classmethod
    async def get_pool(cls) -> aiohttp.ClientSession:
        if cls._pool is None:
            connector = aiohttp.TCPConnector(
                limit=100,  # Total connections
                limit_per_host=10,  # Per host
                ttl_dns_cache=300
            )
            cls._pool = aiohttp.ClientSession(connector=connector)
        return cls._pool
```

### Custom Ranker with Caching

```python
from functools import lru_cache

class CachedRanker(BaseRanker):
    @lru_cache(maxsize=10000)
    def compute_relevance(self, item_id: str, keywords: tuple) -> float:
        # Expensive computation cached
        pass
```

### Custom Storage Backend

```python
class PostgreSQLStorage(BaseStorage):
    async def batch_insert(self, items: List[Item]):
        # Use COPY for bulk insert (100x faster than INSERT)
        async with self.pool.acquire() as conn:
            await conn.copy_records_to_table(
                'items',
                records=items,
                columns=['id', 'title', ...]
            )
```

## Summary

This architecture balances:
- **Simplicity**: Runs locally with one command
- **Performance**: Async I/O, batch processing, indexing
- **Scalability**: Patterns support 10x-100x growth
- **Extensibility**: Add sources without code changes

Start local, scale when needed.
