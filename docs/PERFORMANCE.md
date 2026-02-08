# Performance Guide

## Benchmarks & Targets

### Ingest Pipeline
| Metric | Target | Optimization |
|--------|--------|--------------|
| Fetch 10 sources (concurrent) | <30s | async/await, connection pooling |
| Parse 1000 RSS items | <2s | Streaming XML parser (iterparse) |
| Insert 1000 items (batch) | <1s | executemany(), WAL mode |
| Snapshot storage | <100ms per item | Async file I/O |

### Denoising & Ranking
| Metric | Target | Optimization |
|--------|--------|--------------|
| Deduplicate 10K items | <10s | MinHash/LSH (O(n) not O(n²)) |
| Score 10K items | <5s | NumPy vectorization |
| Generate 50 summaries (LLM) | <30s | Batch API calls (10 concurrent) |

### Search & API
| Metric | Target | Optimization |
|--------|--------|--------------|
| FTS search (10K items) | <500ms | FTS5 indexes, query optimization |
| FTS search (100K items) | <1s | Partitioning, rank caching |
| API response (cached) | <50ms | In-memory cache, SSR |
| API response (uncached) | <200ms | Connection pooling, prepared statements |

### UI
| Metric | Target | Optimization |
|--------|--------|--------------|
| Lighthouse Performance | >90 | SSR, code splitting, image optimization |
| First Contentful Paint | <1.5s | Server components, minimal JS |
| Time to Interactive | <3s | Lazy loading, defer non-critical |
| Search debounce | 300ms | Client-side debouncing |

## Profiling

### Python Backend

**CPU Profiling**:
```bash
python -m cProfile -o profile.stats backend/pipeline/cli.py ingest --all
python -m pstats profile.stats
# (pstats) sort cumtime
# (pstats) stats 20
```

**Memory Profiling**:
```bash
pip install memory_profiler
python -m memory_profiler backend/pipeline/cli.py ingest --all
```

**Async Profiling**:
```python
import asyncio
import cProfile

async def main():
    # Your async code
    pass

cProfile.run('asyncio.run(main())')
```

### SQLite Query Analysis

**Explain Query Plan**:
```bash
sqlite3 data/ainews.db

sqlite> EXPLAIN QUERY PLAN
   ...> SELECT items.*, metrics.score
   ...> FROM items_fts
   ...> JOIN items ON items.rowid = items_fts.rowid
   ...> WHERE items_fts MATCH 'LLM agents'
   ...> ORDER BY metrics.score DESC;
```

**Analyze Statistics**:
```bash
sqlite3 data/ainews.db "ANALYZE;"
```

**Check Index Usage**:
```sql
-- Should use index, not full table scan
EXPLAIN QUERY PLAN SELECT * FROM items WHERE category = 'news';
-- Expected: SEARCH items USING INDEX idx_items_category
```

### Next.js Performance

**Build Analysis**:
```bash
ANALYZE=true npm run build
# Opens bundle analyzer in browser
```

**Lighthouse CI**:
```bash
npm install -g @lhci/cli
lhci autorun --collect.url=http://localhost:3000
```

**React DevTools Profiler**:
1. Install React DevTools extension
2. Open DevTools → Profiler tab
3. Click Record → Interact with app → Stop
4. Analyze render times

## Optimization Strategies

### 1. Database Optimization

**WAL Mode** (concurrent reads):
```sql
PRAGMA journal_mode=WAL;
-- Allows readers while writer is active
```

**Increase Cache** (64MB):
```sql
PRAGMA cache_size=-64000;
-- Negative = KB, positive = pages
```

**Optimize Temp Storage**:
```sql
PRAGMA temp_store=MEMORY;
-- Keep temp tables in memory
```

**Synchronous Mode**:
```sql
PRAGMA synchronous=NORMAL;
-- FULL is safer but slower; NORMAL is sufficient with WAL
```

**Auto Vacuum**:
```sql
PRAGMA auto_vacuum=INCREMENTAL;
-- Prevents DB bloat, run: PRAGMA incremental_vacuum(N);
```

**Batch Inserts**:
```python
# BAD: One transaction per insert
for item in items:
    cursor.execute("INSERT ...", item)

# GOOD: Batch transaction
cursor.executemany("INSERT ...", items)
```

### 2. FTS5 Optimization

**Custom Tokenizer** (multilingual):
```sql
CREATE VIRTUAL TABLE items_fts USING fts5(
    title, content,
    tokenize='porter unicode61 remove_diacritics 2'
);
-- porter: English stemming
-- unicode61: Unicode support (Japanese, etc.)
-- remove_diacritics: Normalize accents
```

**Rank Caching**:
```sql
-- Store precomputed rank in metrics table
UPDATE metrics SET fts_rank = (
    SELECT rank FROM items_fts WHERE items_fts.rowid = items.rowid
);

-- Then query cached rank
SELECT * FROM items JOIN metrics ON items.id = metrics.item_id
ORDER BY metrics.fts_rank DESC;
```

**Partial Indexes** (common filters):
```sql
CREATE INDEX idx_news_recent ON items(published_at DESC)
WHERE category = 'news' AND published_at > date('now', '-7 days');
-- Only indexes recent news
```

### 3. Connector Optimization

**Connection Pooling**:
```python
import aiohttp

connector = aiohttp.TCPConnector(
    limit=100,           # Total connections
    limit_per_host=10,   # Per host
    ttl_dns_cache=300,   # DNS cache TTL
    keepalive_timeout=30 # Keep connections alive
)

session = aiohttp.ClientSession(connector=connector)
```

**Concurrent Fetching**:
```python
import asyncio

async def fetch_all(sources):
    # Limit concurrency with semaphore
    sem = asyncio.Semaphore(10)

    async def fetch_limited(source):
        async with sem:
            return await fetch_source(source)

    tasks = [fetch_limited(s) for s in sources]
    return await asyncio.gather(*tasks, return_exceptions=True)
```

**Streaming XML Parser** (low memory):
```python
from lxml import etree

async def parse_large_rss(url):
    async with session.get(url) as resp:
        # Stream parse instead of loading entire XML
        async for event, elem in etree.iterparse(resp.content):
            if elem.tag == 'item':
                yield parse_item(elem)
                elem.clear()  # Free memory
```

### 4. Deduplication Optimization

**MinHash for O(n) Dedup**:
```python
from datasketch import MinHash, MinHashLSH

# Create LSH index
lsh = MinHashLSH(threshold=0.85, num_perm=128)

# Add items
for item in items:
    mh = MinHash(num_perm=128)
    for word in item.title.split():
        mh.update(word.encode('utf8'))
    lsh.insert(item.id, mh)

# Query for duplicates (O(1) instead of O(n))
for item in new_items:
    mh = compute_minhash(item)
    duplicates = lsh.query(mh)  # Fast!
```

**Cache TF-IDF Vectors**:
```python
from joblib import Memory

memory = Memory('./cache', verbose=0)

@memory.cache
def compute_tfidf(corpus):
    # Expensive computation cached to disk
    return TfidfVectorizer().fit_transform(corpus)
```

### 5. LLM Optimization

**Batch API Calls**:
```python
import asyncio
from openai import AsyncOpenAI

client = AsyncOpenAI()

async def batch_summarize(items, batch_size=10):
    for i in range(0, len(items), batch_size):
        batch = items[i:i+batch_size]
        tasks = [summarize_one(item) for item in batch]
        results = await asyncio.gather(*tasks)
        yield results
```

**Cache Summaries**:
```python
# Check cache first
cached = db.execute(
    "SELECT summary_json FROM metrics WHERE item_id = ?",
    item.id
).fetchone()

if cached:
    return cached['summary_json']

# Generate if not cached
summary = await llm.summarize(item)
db.execute(
    "UPDATE metrics SET summary_json = ? WHERE item_id = ?",
    json.dumps(summary), item.id
)
```

### 6. Next.js Optimization

**Server Components** (default):
```tsx
// app/page.tsx - Server Component (no client JS)
export default async function Page() {
  const data = await fetchData();  // Runs on server
  return <Display data={data} />;
}
```

**Client Components** (minimal):
```tsx
// Only use 'use client' when needed (interactivity)
'use client';
export function SearchInput() {
  const [query, setQuery] = useState('');
  return <input onChange={e => setQuery(e.target.value)} />;
}
```

**API Caching**:
```typescript
export async function GET(request: Request) {
  const data = await fetchData();

  return Response.json(data, {
    headers: {
      'Cache-Control': 'public, s-maxage=3600, stale-while-revalidate=86400'
    }
  });
}
```

**Image Optimization**:
```tsx
import Image from 'next/image';

<Image
  src="/logo.png"
  width={200}
  height={100}
  alt="Logo"
  loading="lazy"  // Lazy load
  placeholder="blur"  // Blur placeholder
/>
```

**Code Splitting**:
```tsx
import dynamic from 'next/dynamic';

const HeavyComponent = dynamic(() => import('./Heavy'), {
  loading: () => <p>Loading...</p>,
  ssr: false  // Don't render on server
});
```

## Monitoring

### Key Metrics to Track

**Ingest Pipeline**:
```python
from prometheus_client import Counter, Histogram

fetch_duration = Histogram(
    'source_fetch_duration_seconds',
    'Source fetch duration',
    ['source_id']
)

fetch_errors = Counter(
    'source_fetch_errors_total',
    'Source fetch errors',
    ['source_id', 'error_type']
)
```

**Database**:
```sql
-- DB size
SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size();

-- FTS index size
SELECT SUM(pgsize) FROM dbstat WHERE name LIKE 'items_fts%';

-- Slow queries (enable with PRAGMA)
PRAGMA query_log=ON;
```

**API**:
```typescript
import { performance } from 'perf_hooks';

const start = performance.now();
const result = await query();
const duration = performance.now() - start;

console.log(`Query took ${duration}ms`);
```

## Troubleshooting

### Slow Ingest

1. **Check concurrent sources**:
   ```yaml
   performance:
     max_concurrent_sources: 20  # Increase
   ```

2. **Profile connectors**:
   ```bash
   python -m cProfile -s cumtime -m backend.pipeline.cli ingest --source slow_source
   ```

3. **Check network latency**:
   ```bash
   time curl -I https://slow-source.com/feed.xml
   ```

### Slow Search

1. **Rebuild FTS index**:
   ```bash
   python -m backend.pipeline.cli rebuild-fts
   ```

2. **Analyze query plan**:
   ```sql
   EXPLAIN QUERY PLAN SELECT * FROM items_fts WHERE items_fts MATCH 'query';
   ```

3. **Vacuum database**:
   ```bash
   python -m backend.pipeline.cli vacuum
   ```

### High Memory Usage

1. **Reduce batch size**:
   ```yaml
   performance:
     batch_size: 500  # Down from 1000
   ```

2. **Disable embeddings**:
   ```yaml
   performance:
     use_embeddings: false
   ```

3. **Profile memory**:
   ```bash
   python -m memory_profiler backend/pipeline/cli.py ingest --all
   ```

### API Timeout

1. **Increase timeout**:
   ```yaml
   performance:
     request_timeout_seconds: 60
   ```

2. **Enable pagination**:
   ```typescript
   const limit = 50;  // Reduce from 100
   ```

3. **Cache responses**:
   ```typescript
   headers: { 'Cache-Control': 'public, max-age=3600' }
   ```

## Best Practices

1. **Always use batch operations** (DB, API)
2. **Cache expensive computations** (embeddings, TF-IDF, summaries)
3. **Use async/await for I/O-bound tasks**
4. **Use multiprocessing for CPU-bound tasks**
5. **Monitor & profile before optimizing**
6. **Test with production-scale data** (not just 10 items)
7. **Set up alerts** (disk space, error rate, API latency)

## Scaling Checklist

- [ ] Ingest completes in <30s for 10 sources
- [ ] Search returns in <1s for 100K items
- [ ] API responses <200ms (uncached)
- [ ] Lighthouse score >90
- [ ] Database size <100MB for 10K items
- [ ] Memory usage <500MB peak
- [ ] No N+1 query problems
- [ ] All slow queries (<100ms) indexed
- [ ] FTS index size <20% of total DB size
- [ ] Logs & metrics exportable (JSON)
