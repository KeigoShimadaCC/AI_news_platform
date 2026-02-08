# Quick Start Guide

Get your AI News Platform running in 5 minutes!

## Prerequisites

- **macOS** (tested on macOS 10.15+)
- **Python 3.11+** (check: `python3 --version`)
- **Node.js 18+** (check: `node --version`)
- **Git** (check: `git --version`)

## Installation

### 1. Clone or Navigate to Project

```bash
cd /Users/keigoshimada/Documents/AI_news_platform
```

### 2. Run Setup Script

```bash
./bin/setup.sh
```

This will:
- Create Python virtual environment
- Install Python dependencies
- Install Node.js dependencies
- Create `.env` from template
- Initialize SQLite database

**Time:** ~2-3 minutes (depending on internet speed)

### 3. Configure API Keys (Optional)

```bash
nano .env  # or use your favorite editor
```

Add your API keys (all optional but recommended):

```env
# LLM for summaries (choose one)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Better rate limits (optional)
GITHUB_TOKEN=ghp_...
QIITA_API_TOKEN=...
```

Save and exit (`Ctrl+O`, `Ctrl+X` in nano).

### 4. Start the Platform

```bash
./bin/start.sh
```

This will:
- Run initial data ingest (first time only)
- Generate today's digest
- Start web UI on http://localhost:3000

**Time:** First run ~30-60 seconds, subsequent runs ~5 seconds

### 5. Open in Browser

```bash
open http://localhost:3000
```

Or manually navigate to: **http://localhost:3000**

## That's It! 🎉

You should see:
- Today's digest with News, Tips, and Papers tabs
- Search functionality
- Source management

## Quick Tour

### Home Page (/)

Daily curated digest with three tabs:
- **News**: Top 20 AI news items
- **Tips**: Top 20 tutorials and how-tos
- **Papers**: Top 10 research papers

Each item shows:
- Title and source
- "Why it matters" summary
- Relevance score
- Publication date

### Search (/search)

Full-text search across all items:
- Search by keywords
- Filter by category, language, date range
- Sort by relevance or date
- Paginated results (50 per page)

### Sources (/sources)

Manage your 11 configured sources:
- Enable/disable sources
- See last fetch time
- Check for errors
- Manually refresh

### Item Detail (/item/[id])

Detailed view of any item:
- Full content
- Score breakdown (authority, recency, popularity, relevance)
- Cluster information (duplicates)
- Source metadata

## Common Tasks

### Refresh All Sources

```bash
./bin/ingest.sh
```

Or click "Refresh Sources" button in the UI.

### Refresh Single Source

```bash
source venv/bin/activate
python -m backend.pipeline.cli ingest --source openai_news
```

### Search from CLI

```bash
source venv/bin/activate
python -m backend.pipeline.cli search "RAG agents"
```

### Check Status

```bash
source venv/bin/activate
python -m backend.pipeline.cli status
```

### Add a New Source

Edit `config.yaml`:

```yaml
sources:
  # Add at the end:
  - id: my_new_source
    type: rss
    url: https://example.com/feed.xml
    category: news
    authority: 0.75
    refresh_hours: 12
    lang: en
```

Then ingest:

```bash
./bin/ingest.sh
```

See `docs/ADD_SOURCE_GUIDE.md` for detailed instructions.

## Scheduled Updates (Optional)

Set up automatic daily ingests:

```bash
./bin/setup.sh --with-schedule
```

This creates macOS launchd tasks:
- **Ingest**: Every 6 hours
- **Digest**: Every day at 8 AM

Check scheduled tasks:

```bash
launchctl list | grep ainews
```

View logs:

```bash
tail -f /tmp/ainews-ingest.log
tail -f /tmp/ainews-digest.log
```

## Stopping the Platform

Press `Ctrl+C` in the terminal where you ran `./bin/start.sh`.

Or kill processes:

```bash
pkill -f "next dev"
```

## Troubleshooting

### "Python 3.11+ required"

Install Python 3.11+:

```bash
brew install python@3.11
```

### "Node.js 18+ required"

Install Node.js:

```bash
brew install node@18
```

### "Database locked"

Stop any running instances:

```bash
pkill -f "next dev"
pkill -f "python.*pipeline"
```

Then restart:

```bash
./bin/start.sh
```

### "Permission denied: ./bin/setup.sh"

Make scripts executable:

```bash
chmod +x bin/*.sh
```

### Sources Failing

Check status:

```bash
source venv/bin/activate
python -m backend.pipeline.cli status --verbose
```

Common fixes:
- Add API tokens to `.env`
- Increase `refresh_hours` in config
- Check network connectivity

### Search Returns Nothing

Rebuild FTS index:

```bash
source venv/bin/activate
python -m backend.pipeline.cli rebuild-fts
```

### "Port 3000 already in use"

Change port:

```bash
PORT=3001 npm run dev
```

## Next Steps

1. **Customize sources**: Edit `config.yaml` to add/remove sources
2. **Tune scoring**: Adjust weights in `config.yaml` → `scoring.weights`
3. **Set quotas**: Limit items per source in `config.yaml` → `scoring.quotas`
4. **Configure LLM**: Change provider in `config.yaml` → `llm.provider`
5. **Schedule updates**: Run `./bin/setup.sh --with-schedule`

## Learn More

- **Full guide**: See `README.md`
- **Add sources**: See `docs/ADD_SOURCE_GUIDE.md`
- **Architecture**: See `docs/ARCHITECTURE.md`
- **Performance**: See `docs/PERFORMANCE.md`
- **Scaling**: See `docs/SCALING.md`

## Getting Help

1. Check logs: `/tmp/ainews-*.log`
2. Run with verbose: `python -m backend.pipeline.cli <command> --verbose`
3. Check README troubleshooting section
4. Review source code: `backend/` and `app/`

## Default Sources (11 Total)

Your platform comes pre-configured with:

**News (5):**
- OpenAI News
- DeepMind Blog
- Hugging Face Blog
- Hacker News (AI topics)
- GitHub (AI repos)

**Tips (4):**
- Zenn (LLM + AI, Japanese)
- Qiita (LLM, Japanese)
- Reddit LocalLLaMA

**Papers (2):**
- arXiv API (cs.CL/AI/LG)
- arXiv RSS (cs.CL)

## Performance Expectations

On a typical macOS laptop:

| Operation | Expected Time |
|-----------|---------------|
| Initial setup | 2-3 minutes |
| First ingest (11 sources) | 30-60 seconds |
| Subsequent ingests | 15-30 seconds |
| Search query | <1 second |
| Digest generation | 10-30 seconds |
| Page load | <2 seconds |

## What's Happening Behind the Scenes?

When you run `./bin/start.sh`:

1. **Activates** Python virtual environment
2. **Checks** if database exists
3. **Runs** initial ingest (first time only):
   - Fetches from 11 sources concurrently
   - Normalizes and deduplicates items
   - Computes relevance scores
   - Stores in SQLite database
4. **Generates** daily digest:
   - Applies filters and quotas
   - Ranks items by score
   - Creates summaries (if LLM configured)
   - Saves digest to database
5. **Starts** Next.js development server
6. **Opens** browser to http://localhost:3000

## Configuration Files

- `config.yaml`: Sources, scoring, quotas
- `.env`: API keys, secrets
- `pyproject.toml`: Python dependencies
- `package.json`: Node.js dependencies

## Data Storage

- `data/ainews.db`: SQLite database (all items, scores, digests)
- `data/snapshots/`: HTML/JSON snapshots of fetched content

## Logs

- `/tmp/ainews-ui.log`: Next.js UI logs
- `/tmp/ainews-ingest.log`: Ingest job logs (if scheduled)
- `/tmp/ainews-digest.log`: Digest generation logs (if scheduled)

## Enjoy Your AI News Platform! 🚀

You now have a local-first, extensible, and fast AI news aggregator running on your machine.

Happy reading! 📰
