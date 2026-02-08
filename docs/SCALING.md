# Scaling Beyond Local

This platform is designed for local-first use but architected to scale. Here's how to evolve it as your needs grow.

## Growth Stages

### Stage 1: Local Single-User (Current)
- **Capacity**: 10-20 sources, 10K-100K items
- **Infrastructure**: SQLite, local Python, Next.js dev server
- **Cost**: $0 (except LLM API)
- **Setup time**: 5 minutes

### Stage 2: Local Power-User
- **Capacity**: 50+ sources, 100K-500K items
- **Upgrades**:
  - Increase concurrent sources (config)
  - Add read replicas (Litestream)
  - Enable embeddings (GPU)
  - Archive old data (6+ months)
- **Cost**: $0
- **Effort**: 1 hour config tuning

### Stage 3: Multi-User Local Network
- **Capacity**: 100+ sources, 1M items, 5-10 users
- **Upgrades**:
  - Deploy Next.js (npm run build + pm2)
  - PostgreSQL instead of SQLite
  - Redis cache layer
  - Nginx reverse proxy
- **Cost**: $0 (self-hosted)
- **Effort**: 1 day setup

### Stage 4: Cloud Deployment
- **Capacity**: 500+ sources, 10M+ items, 100+ users
- **Upgrades**:
  - Deploy to Vercel/Netlify (UI)
  - AWS/GCP for backend workers
  - Managed PostgreSQL (RDS/Cloud SQL)
  - Managed Redis (ElastiCache/Memorystore)
  - Message queue (SQS/Pub/Sub)
- **Cost**: $50-500/month
- **Effort**: 1 week setup

## Migration Paths

### SQLite → PostgreSQL

**Why**: SQLite is single-writer; PostgreSQL handles concurrent writes better.

**When**:
- You need >1 concurrent writer (multiple ingest workers)
- Data >1GB
- Need advanced features (materialized views, partitioning)

**How**:

1. **Install PostgreSQL**:
```bash
brew install postgresql@15
brew services start postgresql@15
createdb ainews
```

2. **Update storage layer** (drop-in replacement):
```python
# backend/storage/db.py
import asyncpg

class PostgreSQLStorage(BaseStorage):
    async def connect(self):
        self.pool = await asyncpg.create_pool(
            'postgresql://localhost/ainews'
        )

    # Same interface, different implementation
```

3. **Migrate data**:
```bash
# Export from SQLite
sqlite3 data/ainews.db .dump > ainews.sql

# Import to PostgreSQL (with conversions)
python scripts/migrate_sqlite_to_pg.py
```

4. **Update FTS** (PostgreSQL uses different syntax):
```sql
-- PostgreSQL full-text search
CREATE INDEX items_fts_idx ON items
USING gin(to_tsvector('english', title || ' ' || content));

-- Query
SELECT * FROM items
WHERE to_tsvector('english', title || ' ' || content) @@ to_tsquery('LLM & agent');
```

### Local → Cloud (Vercel + Railway)

**Setup**:

1. **Deploy UI to Vercel**:
```bash
npm install -g vercel
vercel login
vercel --prod
```

2. **Deploy Backend to Railway**:
```bash
# Create railway.json
{
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "python -m backend.pipeline.cli serve",
    "healthcheckPath": "/health"
  }
}

railway login
railway up
```

3. **Database to Neon/Supabase**:
```bash
# Neon (PostgreSQL)
DATABASE_URL=postgresql://user:pass@neon.tech/ainews

# Or Supabase
DATABASE_URL=postgresql://postgres:pass@db.supabase.co/postgres
```

4. **Update environment**:
```env
# .env.production
DATABASE_URL=postgresql://...
REDIS_URL=redis://...
NEXT_PUBLIC_API_URL=https://api.ainews.com
```

## Performance at Scale

### Horizontal Scaling (Ingest Workers)

**Problem**: Single worker can't keep up with 100+ sources.

**Solution**: Multiple workers via message queue.

```
┌─────────────┐     ┌─────────────┐
│  Scheduler  │────▶│    Queue    │ (RabbitMQ/SQS)
└─────────────┘     └──────┬──────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
    ┌────▼────┐       ┌────▼────┐       ┌────▼────┐
    │ Worker1 │       │ Worker2 │       │ Worker N│
    └────┬────┘       └────┬────┘       └────┬────┘
         │                 │                 │
         └─────────────────┼─────────────────┘
                           │
                     ┌─────▼──────┐
                     │ PostgreSQL │
                     └────────────┘
```

**Implementation**:

```python
# producer.py
import pika

connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()
channel.queue_declare(queue='sources', durable=True)

for source in sources:
    channel.basic_publish(
        exchange='',
        routing_key='sources',
        body=json.dumps(source),
        properties=pika.BasicProperties(delivery_mode=2)
    )

# worker.py
def callback(ch, method, properties, body):
    source = json.loads(body)
    ingest_source(source)
    ch.basic_ack(delivery_tag=method.delivery_tag)

channel.basic_consume(queue='sources', on_message_callback=callback)
channel.start_consuming()
```

### Read Replicas (High Read Load)

**Problem**: UI queries slow down ingest writes.

**Solution**: PostgreSQL streaming replication.

```
Primary (write) ──▶ Replica1 (read) ──▶ UI queries
                │
                └──▶ Replica2 (read) ──▶ API queries
```

**Setup**:
```bash
# On primary
wal_level = replica
max_wal_senders = 10

# On replica
primary_conninfo = 'host=primary port=5432 user=replicator'
```

**Application routing**:
```python
class DatabaseRouter:
    def read(self):
        return random.choice([replica1, replica2])

    def write(self):
        return primary

# Usage
items = db.read().query("SELECT ...")  # Hits replica
db.write().execute("INSERT ...")  # Hits primary
```

### Caching Layer (Redis)

**Problem**: Same queries repeated (digest, popular searches).

**Solution**: Cache API responses in Redis.

```python
import redis
import json

cache = redis.Redis(host='localhost', port=6379, db=0)

async def get_digest(date: str):
    # Check cache
    cached = cache.get(f'digest:{date}')
    if cached:
        return json.loads(cached)

    # Generate
    digest = await generate_digest(date)

    # Cache for 1 hour
    cache.setex(f'digest:{date}', 3600, json.dumps(digest))

    return digest
```

### Partitioning (Large Datasets)

**Problem**: 10M+ items, queries slow even with indexes.

**Solution**: Partition by date.

```sql
-- PostgreSQL partitioning
CREATE TABLE items (
    id TEXT,
    published_at TIMESTAMP,
    ...
) PARTITION BY RANGE (published_at);

CREATE TABLE items_2025_01 PARTITION OF items
FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');

CREATE TABLE items_2025_02 PARTITION OF items
FOR VALUES FROM ('2025-02-01') TO ('2025-03-01');

-- Queries automatically route to correct partition
SELECT * FROM items WHERE published_at > '2025-02-01';
-- Only scans items_2025_02
```

## Cost Optimization

### Free Tier Setup

- **UI**: Vercel (free for hobby)
- **Database**: Supabase (500MB free)
- **Redis**: Upstash (10K requests/day free)
- **Workers**: Railway (500 hours/month free)
- **LLM**: OpenAI free tier → Local Ollama

**Total**: $0/month for small-scale

### Production Setup (~100 users)

- **UI**: Vercel Pro ($20/month)
- **Database**: Neon Pro ($25/month, 10GB)
- **Redis**: Upstash Pro ($10/month)
- **Workers**: Railway ($10/month)
- **LLM**: GPT-4o-mini (~$20/month for 50K summaries)

**Total**: ~$85/month

### Enterprise Setup (1000+ users)

- **UI**: Vercel Enterprise ($150/month) or self-hosted
- **Database**: AWS RDS PostgreSQL ($100/month)
- **Redis**: ElastiCache ($50/month)
- **Workers**: ECS/Kubernetes ($100/month)
- **LLM**: Self-hosted Llama ($0) or GPT-4 ($200/month)
- **Monitoring**: Datadog/New Relic ($50/month)

**Total**: ~$650/month

## Advanced Features

### Real-Time Updates (WebSocket)

```typescript
// app/components/LiveDigest.tsx
'use client';
import { useEffect } from 'react';
import io from 'socket.io-client';

export function LiveDigest() {
  useEffect(() => {
    const socket = io('ws://localhost:8000');

    socket.on('new_items', (items) => {
      // Update UI in real-time
      setItems(prev => [...items, ...prev]);
    });

    return () => socket.disconnect();
  }, []);
}
```

```python
# backend/websocket.py
import socketio

sio = socketio.AsyncServer(async_mode='asgi')

async def broadcast_new_items(items):
    await sio.emit('new_items', items)
```

### Machine Learning Features

**Better Deduplication** (Sentence Transformers):
```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('all-MiniLM-L6-v2')

embeddings = model.encode([item.title for item in items])
similarity_matrix = cosine_similarity(embeddings)
# Cluster based on similarity
```

**Personalized Ranking** (User preferences):
```python
class PersonalizedRanker:
    def rank(self, items: List[Item], user_profile: UserProfile) -> List[Item]:
        for item in items:
            # Boost score based on user interests
            if any(tag in user_profile.interests for tag in item.tags):
                item.score *= 1.5

        return sorted(items, key=lambda x: x.score, reverse=True)
```

**Trend Detection** (Emerging topics):
```python
from collections import Counter

def detect_trends(items: List[Item], window_days: int = 7) -> List[str]:
    recent = [i for i in items if i.days_ago <= window_days]
    older = [i for i in items if window_days < i.days_ago <= window_days * 2]

    recent_keywords = Counter(word for i in recent for word in i.title.split())
    older_keywords = Counter(word for i in older for word in i.title.split())

    # Find keywords with increasing frequency
    trends = []
    for keyword, recent_count in recent_keywords.items():
        older_count = older_keywords.get(keyword, 0)
        if recent_count > older_count * 2:  # 2x increase
            trends.append(keyword)

    return trends
```

### Monitoring & Alerting

**Prometheus + Grafana**:
```python
# backend/monitoring/prometheus.py
from prometheus_client import start_http_server, Counter, Histogram

fetch_duration = Histogram('source_fetch_duration', 'Source fetch time', ['source_id'])
fetch_errors = Counter('source_fetch_errors', 'Source fetch errors', ['source_id'])

# Expose metrics
start_http_server(8001)
```

**Grafana Dashboard**:
```json
{
  "title": "AI News Platform",
  "panels": [
    {
      "title": "Ingest Duration",
      "targets": ["rate(source_fetch_duration_sum[5m])"]
    },
    {
      "title": "Error Rate",
      "targets": ["rate(source_fetch_errors_total[5m])"]
    }
  ]
}
```

**Alerts**:
```yaml
# alerts.yml
groups:
  - name: ainews
    rules:
      - alert: HighErrorRate
        expr: rate(source_fetch_errors_total[5m]) > 0.1
        annotations:
          summary: "High error rate on {{ $labels.source_id }}"

      - alert: SlowIngest
        expr: source_fetch_duration_seconds > 60
        annotations:
          summary: "Slow ingest on {{ $labels.source_id }}"
```

## Migration Checklist

### Local → Production

- [ ] Environment variables configured (.env.production)
- [ ] Database migrated (SQLite → PostgreSQL)
- [ ] Indexes created & analyzed
- [ ] API keys secured (secrets manager)
- [ ] CORS configured (allowed origins)
- [ ] Rate limiting enabled (API routes)
- [ ] Monitoring setup (logs, metrics)
- [ ] Backups automated (daily snapshots)
- [ ] SSL/TLS enabled (HTTPS)
- [ ] CDN configured (static assets)
- [ ] Health checks endpoint (/health)
- [ ] Graceful shutdown (SIGTERM handler)
- [ ] Load testing (100+ concurrent users)
- [ ] Disaster recovery plan documented

## Summary

This platform scales from:
- **1 user, 10 sources, 10K items** (laptop)
  → **1000 users, 500 sources, 10M items** (cloud)

Key scaling patterns:
1. **Vertical**: Bigger machine, more RAM/CPU
2. **Horizontal**: More workers, read replicas
3. **Partitioning**: Shard by date/source
4. **Caching**: Redis for hot data
5. **Async**: Non-blocking I/O everywhere

Start simple. Scale when needed. Monitor always.
