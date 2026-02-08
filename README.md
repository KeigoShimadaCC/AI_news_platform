# AI News Platform

> A local-first, extensible AI news aggregation platform for macOS

## Features

- **Local-First**: All data stored locally in SQLite with WAL mode
- **Extensible**: Add new sources by editing `config.yaml` - no code required
- **Fast**: Sub-second search with FTS5, digest generation in <30s
- **Intelligent**: Deduplication, denoising, and relevance-based ranking
- **Resilient**: Per-source failure isolation, circuit breakers, retry logic
- **Scalable**: Async I/O, batch processing, connection pooling

## Quick Start

```bash
# 1. Install dependencies
./bin/setup.sh

# 2. Configure (optional)
cp .env.example .env
# Edit .env with your API keys

# 3. Start the platform
./bin/start.sh

# 4. Open browser
open http://localhost:3000
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         Next.js UI                           │
│          (Digest View, Search, Source Management)            │
└────────────────────┬────────────────────────────────────────┘
                     │
                     │ API Routes
                     │
┌────────────────────▼────────────────────────────────────────┐
│                   Python Backend                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  Connectors  │→ │  Pipeline    │→ │  Denoise &   │      │
│  │  (RSS/API)   │  │  Orchestrator│  │  Ranking     │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│                           │                                  │
│                           ▼                                  │
│                  ┌─────────────────┐                        │
│                  │  SQLite + FTS5  │                        │
│                  └─────────────────┘                        │
└─────────────────────────────────────────────────────────────┘
```

## Project Structure

```
AI_news_platform/
├── backend/                 # Python backend
│   ├── connectors/         # Source connectors (RSS, API, Scrape)
│   ├── storage/            # Database layer & models
│   ├── pipeline/           # Ingest orchestration & CLI
│   ├── denoise/            # Filtering & deduplication
│   └── digest/             # Ranking & summarization
├── app/                    # Next.js frontend
│   ├── api/                # API routes
│   ├── search/             # Search page
│   ├── sources/            # Source management
│   └── item/[id]/          # Item details
├── data/                   # Local data storage
│   ├── ainews.db           # SQLite database
│   └── snapshots/          # HTML/JSON snapshots
├── bin/                    # Utility scripts
│   ├── setup.sh            # Installation
│   ├── start.sh            # Startup
│   └── ingest.sh           # Manual ingest trigger
├── launchd/                # macOS scheduled tasks
├── tests/                  # Test suites
├── docs/                   # Documentation
├── config.yaml             # Source & scoring configuration
└── .env                    # Environment variables
```

## Usage

### Daily Digest

The home page shows today's curated digest:
- **News**: Top 20 AI news items
- **Tips**: Top 20 practical tips & tutorials
- **Papers**: Top 10 research papers

Each item includes:
- Title & source
- "Why it matters" summary
- Relevance score breakdown
- Publication date & popularity metrics

### Search

Full-text search across all items:
```
/search?q=RAG&category=tips&lang=en&days=7
```

Filters:
- Category (news/tips/paper)
- Language (en/ja)
- Date range
- Source
- Minimum score

### Source Management

`/sources` page shows:
- All configured sources
- Last fetch timestamp
- Error status
- Enable/disable toggle
- Manual refresh button

### Manual Operations

```bash
# Ingest all sources
python -m backend.pipeline.cli ingest --all

# Ingest specific source
python -m backend.pipeline.cli ingest --source openai_news

# Generate digest
python -m backend.pipeline.cli digest

# Show status
python -m backend.pipeline.cli status

# Search from CLI
python -m backend.pipeline.cli search "LLM agents"

# Vacuum & optimize
python -m backend.pipeline.cli vacuum
```

## Adding a New Source

### 1. Edit `config.yaml`

```yaml
sources:
  - id: my_new_source
    type: rss                    # or: api, rss_or_scrape
    url: https://example.com/feed.xml
    category: news               # news, tips, or paper
    authority: 0.75              # 0.0 to 1.0
    refresh_hours: 12
    lang: en
    # Optional:
    user_agent: "Custom UA"
    headers:
      Authorization: "Bearer ${MY_TOKEN}"
    params:
      limit: 50
```

### 2. Add to quotas (optional)

```yaml
scoring:
  quotas:
    my_new_source: 15
```

### 3. Test

```bash
python -m backend.pipeline.cli ingest --source my_new_source
```

That's it! No code changes needed.

## Advanced: Adding a New Connector Type

If RSS/API aren't enough, implement a custom connector:

```python
# backend/connectors/custom.py
from backend.connectors.base import BaseConnector

class CustomConnector(BaseConnector):
    async def fetch(self) -> List[Dict]:
        # Your custom logic
        return items
```

Update config:
```yaml
  - id: custom_source
    type: custom  # Maps to CustomConnector
    # ...
```

## Performance Tuning

### Database Optimization

```bash
# Analyze query performance
sqlite3 data/ainews.db "ANALYZE"

# Check index usage
python -m backend.pipeline.cli explain-query "SELECT * FROM items WHERE ..."
```

### Concurrent Sources

Edit `config.yaml`:
```yaml
performance:
  max_concurrent_sources: 20  # Increase for more parallelism
  request_timeout_seconds: 60  # Adjust for slow sources
```

### Batch Size

For large ingests:
```yaml
performance:
  batch_size: 2000  # Larger batches = faster, more memory
```

### Embeddings for Better Dedup

```yaml
performance:
  use_embeddings: true
```

Requires: `pip install sentence-transformers`

## Troubleshooting

### Source Fetch Fails

Check `/sources` page for error details, or:
```bash
python -m backend.pipeline.cli status --verbose
```

Common issues:
- **Rate limiting**: Increase `refresh_hours` or add API token
- **Blocked UA**: Set custom `user_agent` in config
- **SSL errors**: Update CA certificates

### Search is Slow

```bash
# Rebuild FTS index
python -m backend.pipeline.cli rebuild-fts

# Vacuum database
python -m backend.pipeline.cli vacuum
```

### High Memory Usage

Reduce:
```yaml
performance:
  batch_size: 500
  max_concurrent_sources: 5
```

### Digest Not Updating

Check schedule:
```bash
launchctl list | grep ainews
launchctl print gui/$(id -u)/com.ainews.ingest
```

Reload:
```bash
./bin/setup.sh --reload-launchd
```

## Development

### Run Tests

```bash
# All tests
pytest

# Specific module
pytest tests/test_connectors.py

# With coverage
pytest --cov=backend --cov-report=html
```

### Code Quality

```bash
# Lint
ruff check .

# Format
ruff format .

# Type check
mypy backend/
```

### Database Migrations

```bash
# Create migration
python -m backend.storage.migrations create "add_new_field"

# Apply migrations
python -m backend.storage.migrations upgrade

# Rollback
python -m backend.storage.migrations downgrade
```

## Scaling Beyond Local

While designed for local-first use, the architecture supports scaling:

1. **Multi-instance ingest**: Run multiple ingest workers with connection pooling
2. **Read replicas**: SQLite's WAL mode supports concurrent readers
3. **Distributed storage**: Replace SQLite with PostgreSQL (connector pattern supports this)
4. **Caching layer**: Add Redis for API response caching
5. **CDN**: Deploy Next.js to Vercel/Netlify for global UI

See `docs/SCALING.md` for details.

## License

MIT

## Credits

Built with:
- [Next.js](https://nextjs.org/) - UI framework
- [SQLite](https://www.sqlite.org/) - Local database
- [FTS5](https://www.sqlite.org/fts5.html) - Full-text search
- [aiohttp](https://docs.aiohttp.org/) - Async HTTP
- [feedparser](https://feedparser.readthedocs.io/) - RSS parsing
- [BeautifulSoup](https://www.crummy.com/software/BeautifulSoup/) - HTML parsing
