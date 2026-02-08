# Systematic approach to scraping article content

When a source gives you a **list** of articles (RSS or API) but **no body text**, you need a reliable way to fetch and store full content. This doc describes the approach used in this project.

## When to fetch article bodies

- **List API returns only metadata** (title, url, date, author) and no `body` or `content`.
- You need the full text for **search**, **summarization**, or **display** in the app.

## Preferred order

1. **Use an official API** that returns body (e.g. Qiita’s API includes `body`). No scraping.
2. **Use RSS/Atom** if the feed includes full or sufficient content in `description`/`content`. No per-article fetch.
3. **Fetch each article URL** only when the list source does not provide body (e.g. Zenn topic API).

## How we fetch and extract body

### 1. Check the website

- Open an article URL in the browser.
- **DevTools → Network**: see if the page loads content via an API (XHR/fetch). If yes, prefer that API over scraping HTML.
- **View Page Source**: look for:
  - `<script id="__NEXT_DATA__">` (Next.js): article data is often in JSON here.
  - JSON-LD `<script type="application/ld+json">`: may contain `articleBody`.
  - Main content in a clear container: `<article>`, `main`, or a class like `.article-content`, `.prose`.

### 2. Extraction order (implemented in `content_fetcher`)

1. **`__NEXT_DATA__`**  
   Parse the JSON and look for the article body (e.g. `props.pageProps.article.body` or similar). Works for many Next.js sites (including Zenn).

2. **JSON-LD**  
   Find `<script type="application/ld+json">` with `@type: "Article"` and use `articleBody` if present.

3. **HTML selectors**  
   Use semantic or common class selectors, in this order:
   - `article`
   - `[data-content]`, `main`
   - `.ArticleContent`, `.article-content`, `.post-content`, `.content`, `.markdown`, `.prose`
   Then take the element’s text (strip tags, collapse whitespace).

4. **Fallback**  
   If nothing else matches, use the largest text block inside `<body>` (e.g. for simple pages).

### 3. Be a good citizen

- **User-Agent**: send a browser-like UA (e.g. Chrome on macOS) so the server doesn’t treat you as a bot.
- **Rate limiting**: limit concurrency (e.g. 3 requests at a time) and add a small delay between requests (e.g. 0.3s) to avoid hammering the site.
- **Timeout**: set a request timeout (e.g. 15s) so one slow page doesn’t block the rest.
- **Truncation**: cap stored body length (e.g. 50k characters) to avoid huge payloads.

## Where it’s implemented

- **`backend/connectors/content_fetcher.py`**  
  - `fetch_article_body(url)` fetches the page and runs the extraction steps above.  
  - Used whenever we have a list of items but no body.

- **Zenn (zenn_llm, zenn_ai)**  
  - List from **public API**: `GET https://zenn.dev/api/articles?topic=llm|ai&order=latest&count=30`.  
  - API does not return body.  
  - After normalizing the list, we call **`_enrich_zenn_content()`** in the API connector: for each article URL we call `fetch_article_body(url)` and set `item["content"]` so the orchestrator stores full text.

## Adding body fetch for another source

1. **List from API**  
   In `backend/connectors/api.py`, add a normalizer for the API response (like `_normalize_zenn_articles`) that fills `url`, `title`, `published_at`, etc., and leaves `content` empty.

2. **Enrich with body**  
   After `_normalize_response()`, if this source never gets body from the API, run an enrichment step that:
   - Iterates over items with a URL and empty content.
   - Calls `fetch_article_body(url)` from `content_fetcher`.
   - Sets `item["content"]` (and optionally truncates).

3. **Rate limiting**  
   Use a semaphore and small delays (as in `_enrich_zenn_content`) so you don’t overload the target site.

4. **Optional: site-specific extraction**  
   If the generic extractor fails (e.g. custom JSON path or selector), add a site-specific branch in `content_fetcher` (e.g. by domain or a flag) and extract body from the known structure.

## Summary

| Step | Action |
|------|--------|
| 1 | Prefer list + body from API/RSS; only fetch per-article when necessary. |
| 2 | Fetch article URL with a browser-like UA and timeout. |
| 3 | Extract body: __NEXT_DATA__ → JSON-LD → HTML selectors → body fallback. |
| 4 | Limit concurrency and add short delays between requests. |
| 5 | Store truncated body in the item’s `content` for search and summarization. |

Zenn is the reference implementation: list from API, then enrich with `content_fetcher` and store full article body.
