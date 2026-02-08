# Project Status: AI News Platform

## Overview

**Goal**: Build a local-first AI news aggregation platform that's scalable, extensible, and fast.

**Status**: 🚧 In Development (4 agents working in parallel)

## Architecture Summary

```
┌─────────────────────────────────────────────────────────────┐
│                     USER INTERFACE (Next.js)                 │
│  Digest View | Search | Source Management | Item Details    │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            │ API Routes (TypeScript)
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                    PYTHON BACKEND                            │
│                                                              │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   │
│  │  Connectors  │   │   Pipeline   │   │   Denoise    │   │
│  │              │   │              │   │   & Rank     │   │
│  │ • RSS        │──▶│ Orchestrator │──▶│              │   │
│  │ • API        │   │              │   │ • Dedup      │   │
│  │ • Scrape     │   │ • Async      │   │ • Score      │   │
│  │              │   │ • Batch      │   │ • Quota      │   │
│  └──────────────┘   └──────┬───────┘   └──────┬───────┘   │
│                             │                   │            │
│                             ▼                   ▼            │
│                    ┌─────────────────────────────────┐      │
│                    │   SQLite + WAL + FTS5           │      │
│                    │                                 │      │
│                    │ Tables: sources, items,         │      │
│                    │         metrics, digests        │      │
│                    └─────────────────────────────────┘      │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              Digest Generator + LLM                  │  │
│  │  • Select top N per category                        │  │
│  │  • Generate "why it matters" summaries              │  │
│  │  • Export markdown + JSON                           │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Team Structure

### 4 Specialized Agents (Parallel Execution)

#### Agent A - Connector Engineer
**Responsibility**: Data ingestion layer
**Status**: 🔄 In Progress
**Deliverables**:
- [ ] BaseConnector (abstract class)
- [ ] RSSConnector (with fallback scraper)
- [ ] APIConnector (generic)
- [ ] ScrapeFallbackConnector
- [ ] ConnectionPoolManager
- [ ] Tests with mocked responses
- [ ] Working sources: OpenAI, arXiv, Zenn (minimum)

**Key Features**:
- Async/concurrent fetching (aiohttp)
- Circuit breaker for failed sources
- Exponential backoff retry
- Rate limiting per source
- Memory-efficient streaming parsers

---

#### Agent B - Storage Engineer
**Responsibility**: Database & pipeline orchestration
**Status**: 🔄 In Progress
**Deliverables**:
- [ ] SQLite schema with FTS5
- [ ] Database manager with connection pooling
- [ ] Data models (items, sources, metrics, digests)
- [ ] Migration system
- [ ] Pipeline orchestrator (coordinates connectors)
- [ ] CLI interface (ingest, search, status, vacuum)
- [ ] Snapshot storage system

**Key Features**:
- WAL mode for concurrent reads
- FTS5 with multilingual tokenizer
- Batch inserts (1000 items/txn)
- Sub-second search on 100K items
- Prepared statements & query caching

---

#### Agent C - Ranking Engineer
**Responsibility**: Intelligence layer (denoise, score, digest)
**Status**: 🔄 In Progress
**Deliverables**:
- [ ] Hard filters (keywords, language, popularity)
- [ ] Deduplication engine (MinHash/LSH)
- [ ] Multi-factor scorer (explainable breakdown)
- [ ] Quota enforcement
- [ ] Digest generator
- [ ] LLM summarizer (OpenAI/Anthropic/local/mock)

**Key Features**:
- O(n) deduplication (not O(n²))
- Explainable scoring: authority + recency + popularity + relevance
- Cached embeddings & summaries
- Batch LLM requests (10 concurrent)
- Incremental clustering

---

#### Agent D - UI Engineer
**Responsibility**: User interface & integration
**Status**: 🔄 In Progress
**Deliverables**:
- [ ] Next.js 14+ app with App Router
- [ ] Home page (digest with tabs)
- [ ] Search page (full-text with filters)
- [ ] Sources page (enable/disable, status)
- [ ] Item detail page (with score breakdown)
- [ ] API routes (digest, search, ingest trigger)
- [ ] launchd plists for macOS scheduling

**Key Features**:
- Server-side rendering (SSR)
- API route caching
- Debounced search (300ms)
- Pagination (50 items/page)
- Lighthouse score >90
- Read-only DB access from UI

---

#### Team Lead (Foundation)
**Responsibility**: Project setup & integration
**Status**: ✅ Complete
**Deliverables**:
- [x] Project structure
- [x] config.yaml (11 example sources)
- [x] pyproject.toml (Python dependencies)
- [x] package.json (Node.js dependencies)
- [x] .env.example
- [x] README.md (comprehensive)
- [x] bin/setup.sh, bin/start.sh, bin/ingest.sh
- [x] docs/ARCHITECTURE.md (scalability patterns)
- [x] docs/PERFORMANCE.md (optimization guide)
- [x] docs/SCALING.md (migration paths)
- [x] .gitignore

## Default Sources (11 Configured)

### News (6 sources)
1. **OpenAI News** - RSS + fallback scraper (authority: 1.0)
2. **DeepMind Blog** - RSS (authority: 0.95)
3. **Hugging Face Blog** - RSS + fallback (authority: 0.85)
4. **Hacker News** - Algolia API (authority: 0.75)
5. **GitHub Repos** - Search API (authority: 0.80)

### Tips (3 sources)
6. **Zenn LLM** - RSS (authority: 0.70, Japanese)
7. **Zenn AI** - RSS (authority: 0.70, Japanese)
8. **Qiita** - API (authority: 0.65, Japanese)
9. **Reddit LocalLLaMA** - RSS (authority: 0.70)

### Papers (2 sources)
10. **arXiv API** - API query (authority: 0.90)
11. **arXiv RSS** - cs.CL feed (authority: 0.85)

## Scalability Features

### Built-In from Day 1
- **Async I/O**: All connectors use aiohttp (non-blocking)
- **Batch Processing**: 1000 items per DB transaction
- **Connection Pooling**: Reuse HTTP connections & DB connections
- **WAL Mode**: SQLite allows concurrent readers
- **FTS5**: Optimized full-text search with custom tokenizers
- **Circuit Breakers**: Failed sources don't break entire pipeline
- **Incremental Updates**: Only recompute changed items
- **Config-Driven**: Add sources without code changes
- **Explainable**: Score breakdown stored in DB
- **Cached**: Embeddings, summaries, TF-IDF vectors

### Scaling Path
```
Local (10 sources, 10K items)
    ↓
Local Power-User (50 sources, 100K items)
    ↓
Multi-User Local Network (100 sources, 1M items, 10 users)
    ↓
Cloud Deployment (500 sources, 10M items, 100+ users)
```

Each stage requires minimal changes:
- Stage 1→2: Config tuning only
- Stage 2→3: PostgreSQL + Redis
- Stage 3→4: Deploy to Vercel/Railway + managed services

## Performance Targets

| Operation | Target | Strategy |
|-----------|--------|----------|
| Ingest 10 sources | <30s | Async/concurrent, connection pooling |
| Search 100K items | <1s | FTS5 indexes, query optimization |
| Deduplicate 10K items | <10s | MinHash/LSH (O(n) not O(n²)) |
| Generate digest | <30s | Batch LLM, cached summaries |
| API response (cached) | <100ms | In-memory cache, SSR |

## Acceptance Criteria

### Functional
- [ ] `bin/start.sh` launches UI on localhost
- [ ] `python -m backend.pipeline.cli ingest --all` completes even if some sources fail
- [ ] Daily digest shows ≤20 news + ≤20 tips + ≤10 papers
- [ ] Search returns results in <1s (FTS5)
- [ ] Adding a new RSS source requires only config.yaml edit

### Non-Functional
- [ ] Resilient: per-source failures isolated
- [ ] Explainable: score breakdown visible
- [ ] Fast: sub-second search on 100K items
- [ ] Extensible: new connector type = 1 new class
- [ ] Scalable: patterns support 10x-100x growth

## Configuration

### Scoring Algorithm
```
score = 0.30 × authority
      + 0.25 × recency
      + 0.20 × popularity
      + 0.20 × relevance
      - 0.05 × dup_penalty

where:
  authority  = source.authority (0-1, from config)
  recency    = exp(-days_ago / 7)
  popularity = normalize(stars|points|score) to [0,1]
  relevance  = keyword_match + optional_embeddings
  dup_penalty = 0 for representative, 0.5-1.0 for duplicates
```

### Quotas
- Per-source limits (default: 20)
- Per-category limits (news:20, tips:20, paper:10)
- Minimum popularity thresholds (e.g., HN: 50 points, GitHub: 50 stars)

### Deduplication
1. URL canonical equality (exact match)
2. Title similarity (TF-IDF cosine >0.85 or MinHash)
3. Optional: Content embeddings (if enabled)

## Dependencies

### Python (Backend)
- **Core**: aiohttp, feedparser, beautifulsoup4, lxml
- **Data**: numpy, scikit-learn, pyyaml
- **DB**: sqlite3 (built-in), sqlalchemy (optional)
- **LLM**: openai, anthropic
- **Utils**: tenacity, click, rich, python-dateutil
- **Dev**: pytest, pytest-asyncio, ruff, mypy

### Node.js (Frontend)
- **Framework**: next, react, react-dom
- **Data**: @tanstack/react-query
- **UI**: tailwindcss, lucide-react, clsx
- **Utils**: date-fns
- **Dev**: typescript, eslint

## File Structure

```
AI_news_platform/
├── backend/
│   ├── connectors/      # Agent A
│   ├── storage/         # Agent B
│   ├── pipeline/        # Agent B
│   ├── denoise/         # Agent C
│   └── digest/          # Agent C
├── app/                 # Agent D
│   ├── api/
│   ├── search/
│   ├── sources/
│   └── item/[id]/
├── bin/                 # Scripts
├── data/                # SQLite + snapshots
├── docs/                # Documentation
├── launchd/             # macOS scheduling
├── tests/               # All agents
├── config.yaml          # Source configuration
├── .env.example         # Environment template
├── pyproject.toml       # Python deps
├── package.json         # Node deps
└── README.md            # User guide
```

## Next Steps

1. **Wait for agents to complete** (tasks #1-4)
2. **Integration testing** (end-to-end)
3. **Performance benchmarking** (verify targets)
4. **Documentation review** (add troubleshooting)
5. **User acceptance** (test with real sources)

## Timeline

- **Day 1**: ✅ Foundation setup (complete)
- **Day 1-2**: 🔄 Parallel agent work (in progress)
- **Day 2**: Integration & testing
- **Day 3**: Polish & documentation
- **Day 3+**: Ready for use!

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Source blocks requests | User-agent tuning, fallback scrapers |
| Rate limiting | Exponential backoff, API tokens |
| Database locks | WAL mode, connection pooling |
| LLM API failures | Circuit breaker, mock fallback |
| Slow search | FTS5 indexes, query optimization |
| High memory usage | Streaming parsers, batch limits |

## Success Metrics

After v1 launch:
- [ ] Successfully ingests from 10+ sources daily
- [ ] Zero downtime (local service)
- [ ] <5 failed sources per day (resilience)
- [ ] Digest generation <30s (performance)
- [ ] Search <1s on 50K+ items (scalability)
- [ ] User can add new source in <5 min (extensibility)

## Future Enhancements (Post-v1)

### Intelligence
- [ ] Personalized ranking (user preferences)
- [ ] Trend detection (emerging topics)
- [ ] Topic clustering (group related items)
- [ ] Sentiment analysis (positive/negative)

### Sources
- [ ] X/Twitter API
- [ ] LinkedIn posts
- [ ] YouTube transcripts
- [ ] Slack communities
- [ ] Discord servers

### Features
- [ ] Email digest (daily summary)
- [ ] Browser extension (save to read)
- [ ] Mobile app (PWA)
- [ ] Collaborative filtering (team recommendations)
- [ ] API access (for other tools)

### Infrastructure
- [ ] Multi-language support (expand beyond en/ja)
- [ ] Vector database (better semantic search)
- [ ] Graph database (relationship mining)
- [ ] Real-time updates (WebSocket)
- [ ] Multi-tenant (support teams)

---

**Last Updated**: 2026-02-07
**Version**: 1.0.0-alpha
**Team**: 4 agents + 1 lead
**Status**: 🚧 Foundation complete, agents building components
