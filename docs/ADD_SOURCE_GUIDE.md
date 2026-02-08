# How to Add a New Source

One of the key design goals is **zero-code source additions**. Here's how to add a new source in under 5 minutes.

## Quick Example

Want to add The Verge AI news? Just edit `config.yaml`:

```yaml
sources:
  # ... existing sources ...

  - id: verge_ai
    type: rss
    url: https://www.theverge.com/rss/ai-artificial-intelligence/index.xml
    category: news
    authority: 0.80
    refresh_hours: 12
    lang: en
```

That's it! No code changes needed.

## Step-by-Step Guide

### 1. Identify Source Type

Choose based on what the source provides:

| Source Type | When to Use | Examples |
|-------------|-------------|----------|
| `rss` | Standard RSS/Atom feed | Blog feeds, news sites |
| `api` | RESTful JSON API | GitHub, Hacker News, Qiita |
| `rss_or_scrape` | RSS with HTML fallback | Sites that may block feeds |
| `scrape` | No RSS/API available | (Use as last resort) |

### 2. Find the Feed/API URL

**For RSS:**
- Look for RSS icon on the website
- Check `/feed`, `/rss`, `/atom.xml` paths
- View page source and search for `application/rss+xml`

**For APIs:**
- Check the developer documentation
- Look for public API endpoints
- Test with curl: `curl -i "https://api.example.com/items"`

### 3. Choose Category

Pick the category that best fits:

- **`news`**: Breaking news, announcements, product launches
- **`tips`**: Tutorials, how-tos, best practices, code examples
- **`paper`**: Research papers, academic publications

### 4. Set Authority

Authority (0.0 to 1.0) affects scoring:

| Authority | When to Use |
|-----------|-------------|
| 0.9 - 1.0 | Official sources (OpenAI, Google, arXiv) |
| 0.8 - 0.9 | Highly reputable (major tech blogs) |
| 0.7 - 0.8 | Well-known community sources (HN, Reddit) |
| 0.6 - 0.7 | Niche but quality sources |
| 0.5 - 0.6 | Experimental or less-vetted sources |

### 5. Configure Refresh Rate

Balance freshness vs. rate limits:

| Refresh Hours | When to Use |
|---------------|-------------|
| 1-6 | Breaking news, high-velocity sources |
| 6-12 | Daily blogs, moderate activity |
| 12-24 | Research, weekly publications |

### 6. Add to `config.yaml`

```yaml
sources:
  - id: my_new_source          # Unique identifier (lowercase, underscores)
    type: rss                   # rss, api, rss_or_scrape, scrape
    url: https://example.com/feed.xml
    category: news              # news, tips, paper
    authority: 0.75             # 0.0 to 1.0
    refresh_hours: 12           # How often to fetch
    lang: en                    # en, ja, etc.
```

### 7. Test the Source

```bash
# Test single source ingest
python -m backend.pipeline.cli ingest --source my_new_source

# Check for errors
python -m backend.pipeline.cli status --verbose
```

### 8. Set Quota (Optional)

Limit how many items from this source appear in the digest:

```yaml
scoring:
  quotas:
    my_new_source: 10  # Max 10 items per digest
```

## Advanced Configuration

### API Sources with Parameters

```yaml
  - id: github_trending
    type: api
    url: https://api.github.com/search/repositories
    params:
      q: "stars:>100 created:>2025-01-01"
      sort: stars
      order: desc
      per_page: 30
    category: news
    authority: 0.80
    refresh_hours: 24
    lang: en
    headers:
      Accept: "application/vnd.github.v3+json"
      Authorization: "Bearer ${GITHUB_TOKEN}"  # From .env
```

### Custom Headers

For sources that require authentication or custom user agents:

```yaml
  - id: protected_source
    type: rss
    url: https://example.com/feed
    headers:
      Authorization: "Bearer ${API_TOKEN}"
      User-Agent: "MyBot/1.0"
    # ...
```

### Popularity Thresholds

Only include items above a certain popularity:

```yaml
scoring:
  min_popularity:
    my_new_source:
      points: 100  # For HN-style points
      # or
      stars: 50    # For GitHub-style stars
      # or
      score: 30    # For Reddit-style scores
```

### Language Filtering

```yaml
  - id: multilang_source
    type: rss
    url: https://example.com/feed
    lang: ja  # Will be filtered if content is in other languages
    # ...
```

## Common Patterns

### Pattern 1: Standard Blog RSS

```yaml
  - id: ai_blog
    type: rss
    url: https://blog.example.com/feed.xml
    category: news
    authority: 0.75
    refresh_hours: 12
    lang: en
```

### Pattern 2: API with Search Query

```yaml
  - id: api_search
    type: api
    url: https://api.example.com/search
    params:
      q: "AI OR machine learning"
      limit: 50
    category: tips
    authority: 0.70
    refresh_hours: 6
    lang: en
```

### Pattern 3: RSS with Fallback Scraper

```yaml
  - id: protected_rss
    type: rss_or_scrape
    url: https://example.com/rss
    category: news
    authority: 0.80
    refresh_hours: 12
    lang: en
    user_agent: "Mozilla/5.0 (compatible; AINewsBot/1.0)"
```

### Pattern 4: Reddit Subreddit

```yaml
  - id: reddit_machinelearning
    type: rss
    url: https://www.reddit.com/r/MachineLearning/.rss
    category: tips
    authority: 0.70
    refresh_hours: 6
    lang: en
```

### Pattern 5: arXiv Category

```yaml
  - id: arxiv_cs_ai
    type: rss
    url: https://rss.arxiv.org/rss/cs.AI
    category: paper
    authority: 0.85
    refresh_hours: 24
    lang: en
```

## Troubleshooting

### Source Returns No Items

1. **Test URL manually:**
   ```bash
   curl -I "https://example.com/feed.xml"
   ```

2. **Check response:**
   - 200 OK → Should work
   - 403 Forbidden → Try custom user-agent
   - 404 Not Found → URL is wrong
   - 500 Error → Source is down

3. **Verify feed format:**
   ```bash
   curl "https://example.com/feed.xml" | head -20
   ```
   Should show XML starting with `<rss>` or `<feed>`

### Source Gets Blocked

Add a custom user agent:

```yaml
  - id: my_source
    type: rss_or_scrape  # Enable fallback
    url: https://example.com/feed
    user_agent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
    # ...
```

### API Rate Limiting

1. **Increase refresh interval:**
   ```yaml
   refresh_hours: 24  # Instead of 6
   ```

2. **Add API token:**
   ```bash
   # In .env
   MY_API_TOKEN=your_token_here
   ```

   ```yaml
   headers:
     Authorization: "Bearer ${MY_API_TOKEN}"
   ```

3. **Reduce items fetched:**
   ```yaml
   params:
     per_page: 10  # Instead of 50
   ```

### Items Not Appearing in Digest

Check scoring and quotas:

```bash
# See item scores
sqlite3 data/ainews.db "SELECT id, title, score FROM metrics ORDER BY score DESC LIMIT 20"

# Check source quota
grep -A 5 "quotas:" config.yaml
```

May need to:
- Increase source quota
- Increase authority
- Lower min_popularity threshold

### Duplicate Items

Sources may overlap. This is OK! The deduplication engine will cluster duplicates and pick the best representative.

## Real-World Examples

### Adding The Verge AI

```yaml
  - id: verge_ai
    type: rss
    url: https://www.theverge.com/rss/ai-artificial-intelligence/index.xml
    category: news
    authority: 0.80
    refresh_hours: 12
    lang: en
```

### Adding LangChain Blog

```yaml
  - id: langchain_blog
    type: rss
    url: https://blog.langchain.dev/feed/
    category: tips
    authority: 0.75
    refresh_hours: 12
    lang: en
```

### Adding Replicate Blog

```yaml
  - id: replicate_blog
    type: rss
    url: https://replicate.com/blog/rss.xml
    category: news
    authority: 0.75
    refresh_hours: 12
    lang: en
```

### Adding Papers with Code (trending)

**Note:** Papers with Code (PwC) is not included in v1 defaults due to reported service instability (e.g. 2025). For v1, prefer **arXiv** (API or RSS) or **Hugging Face Daily Papers** for papers. You can add PwC as an optional source if the service is available.

```yaml
  - id: papers_with_code
    type: api
    url: https://paperswithcode.com/api/v1/papers/
    params:
      ordering: "-stars_count"
      items_per_page: 30
    category: paper
    authority: 0.85
    refresh_hours: 24
    lang: en
```

### Adding Lobsters

```yaml
  - id: lobsters
    type: rss
    url: https://lobste.rs/rss
    category: news
    authority: 0.70
    refresh_hours: 6
    lang: en
```

## Best Practices

1. **Start with low authority** (0.6-0.7) and adjust based on quality
2. **Set appropriate quotas** to prevent source dominance
3. **Test before committing** to config
4. **Monitor error rates** via `/sources` page
5. **Use specific categories** for better filtering
6. **Respect rate limits** - prefer longer refresh intervals
7. **Add API tokens** when available (better rate limits)
8. **Document custom sources** in your own notes

## When Code is Required

You only need code changes if:

1. **New connector type** (beyond RSS/API/scrape)
   - Example: WebSocket feeds, GraphQL APIs
   - Create new class extending `BaseConnector`

2. **Complex authentication** (OAuth, JWT)
   - Implement in custom connector

3. **Non-standard data format** (custom XML, binary)
   - Add parser in connector

4. **Complex API pagination** (cursor-based, etc.)
   - Override `fetch()` method in connector

For 95% of sources, config-only is enough!

## Checklist

- [ ] Identified source type (RSS/API/scrape)
- [ ] Found feed/API URL
- [ ] Tested URL manually (curl)
- [ ] Chosen category (news/tips/paper)
- [ ] Set authority (0.0-1.0)
- [ ] Set refresh hours
- [ ] Added to config.yaml
- [ ] Tested ingest: `python -m backend.pipeline.cli ingest --source <id>`
- [ ] Checked status: `python -m backend.pipeline.cli status`
- [ ] Set quota (optional)
- [ ] Verified items in digest
- [ ] Documented (if custom/complex)

## Getting Help

If you're stuck:

1. Check logs: `tail -f /tmp/ainews-ingest.log`
2. Run with verbose: `python -m backend.pipeline.cli ingest --source <id> --verbose`
3. Test URL separately: `curl -v "URL"`
4. Check existing similar sources in config.yaml
5. Consult connector code: `backend/connectors/`

Happy source hunting! 🎯
