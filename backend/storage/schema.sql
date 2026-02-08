-- AI News Platform Schema
-- SQLite with FTS5, WAL mode, optimized indexes

-- Performance pragmas (applied at connection time, not here)
-- PRAGMA journal_mode=WAL;
-- PRAGMA synchronous=NORMAL;
-- PRAGMA cache_size=-64000;
-- PRAGMA temp_store=MEMORY;
-- PRAGMA foreign_keys=ON;

-- Schema versioning
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    description TEXT
);

-- Sources: connector configurations and status tracking
CREATE TABLE IF NOT EXISTS sources (
    id TEXT PRIMARY KEY,
    config JSON NOT NULL,
    last_fetch_at TIMESTAMP,
    last_error TEXT,
    error_count INTEGER DEFAULT 0,
    enabled BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Items: the core content table
CREATE TABLE IF NOT EXISTS items (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    external_id TEXT,
    url TEXT NOT NULL,
    url_canonical TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT,
    author TEXT,
    published_at TIMESTAMP NOT NULL,
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    category TEXT NOT NULL CHECK (category IN ('news', 'tips', 'paper')),
    language TEXT NOT NULL,
    metadata JSON,
    snapshot_path TEXT,
    FOREIGN KEY (source_id) REFERENCES sources(id)
);

-- Metrics: scoring and clustering data per item
CREATE TABLE IF NOT EXISTS metrics (
    item_id TEXT PRIMARY KEY,
    score REAL NOT NULL,
    score_authority REAL,
    score_recency REAL,
    score_popularity REAL,
    score_relevance REAL,
    dup_penalty REAL,
    cluster_id TEXT,
    summary_json JSON,
    computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (item_id) REFERENCES items(id)
);

-- Digests: generated daily summaries by section
CREATE TABLE IF NOT EXISTS digests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date DATE NOT NULL,
    section TEXT NOT NULL CHECK (section IN ('news', 'tips', 'paper')),
    content_markdown TEXT NOT NULL,
    content_json JSON NOT NULL,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(date, section)
);

-- FTS5 full-text search index on items
-- porter: English stemming, unicode61: Unicode normalization, remove_diacritics 2: aggressive diacritics removal
CREATE VIRTUAL TABLE IF NOT EXISTS items_fts USING fts5(
    title,
    content,
    content='items',
    content_rowid='rowid',
    tokenize='porter unicode61 remove_diacritics 2'
);

-- Triggers to keep FTS index in sync with items table
CREATE TRIGGER IF NOT EXISTS items_ai AFTER INSERT ON items BEGIN
    INSERT INTO items_fts(rowid, title, content) VALUES (new.rowid, new.title, new.content);
END;

CREATE TRIGGER IF NOT EXISTS items_ad AFTER DELETE ON items BEGIN
    INSERT INTO items_fts(items_fts, rowid, title, content) VALUES('delete', old.rowid, old.title, old.content);
END;

CREATE TRIGGER IF NOT EXISTS items_au AFTER UPDATE ON items BEGIN
    INSERT INTO items_fts(items_fts, rowid, title, content) VALUES('delete', old.rowid, old.title, old.content);
    INSERT INTO items_fts(rowid, title, content) VALUES (new.rowid, new.title, new.content);
END;

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_items_category ON items(category);
CREATE INDEX IF NOT EXISTS idx_items_published ON items(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_items_source ON items(source_id);
CREATE INDEX IF NOT EXISTS idx_items_canonical ON items(url_canonical);
CREATE INDEX IF NOT EXISTS idx_items_ingested ON items(ingested_at DESC);
CREATE INDEX IF NOT EXISTS idx_items_language ON items(language);
CREATE INDEX IF NOT EXISTS idx_items_source_published ON items(source_id, published_at DESC);
CREATE INDEX IF NOT EXISTS idx_metrics_score ON metrics(score DESC);
CREATE INDEX IF NOT EXISTS idx_metrics_cluster ON metrics(cluster_id);
CREATE INDEX IF NOT EXISTS idx_digests_date ON digests(date DESC);
