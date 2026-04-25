"""SQLite-backed state for dedup and post history."""

from __future__ import annotations

import hashlib
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class PostRecord:
    id: int
    article_hash: str
    article_title: str
    article_url: str
    tweet_text: str
    tweet_id: str | None
    posted_at: int
    dry_run: int


SCHEMA = """
CREATE TABLE IF NOT EXISTS seen_articles (
    article_hash TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    topic TEXT NOT NULL,
    source TEXT NOT NULL,
    first_seen INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    article_hash TEXT NOT NULL,
    article_title TEXT NOT NULL,
    article_url TEXT NOT NULL,
    tweet_text TEXT NOT NULL,
    tweet_id TEXT,
    posted_at INTEGER NOT NULL,
    dry_run INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_posts_posted_at ON posts(posted_at);
"""


def article_hash(url: str, title: str) -> str:
    """Stable identifier for an article. URL is primary; title is a fallback dedup signal."""
    base = f"{url.strip().lower()}|{title.strip().lower()}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:24]


class Store:
    def __init__(self, db_path: str | Path = "data/state.db"):
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    # --- seen articles ---
    def is_seen(self, h: str) -> bool:
        cur = self.conn.execute(
            "SELECT 1 FROM seen_articles WHERE article_hash = ?", (h,)
        )
        return cur.fetchone() is not None

    def mark_seen(self, h: str, title: str, url: str, topic: str, source: str) -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO seen_articles(article_hash, title, url, topic, source, first_seen) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (h, title, url, topic, source, int(time.time())),
        )
        self.conn.commit()

    # --- posts ---
    def record_post(
        self,
        article_hash: str,
        title: str,
        url: str,
        tweet_text: str,
        tweet_id: str | None,
        dry_run: bool,
    ) -> int:
        cur = self.conn.execute(
            "INSERT INTO posts(article_hash, article_title, article_url, tweet_text, tweet_id, posted_at, dry_run) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                article_hash,
                title,
                url,
                tweet_text,
                tweet_id,
                int(time.time()),
                1 if dry_run else 0,
            ),
        )
        self.conn.commit()
        return cur.lastrowid or 0

    def last_post_time(self, real_only: bool = True) -> int | None:
        q = "SELECT MAX(posted_at) AS t FROM posts"
        if real_only:
            q += " WHERE dry_run = 0"
        cur = self.conn.execute(q)
        row = cur.fetchone()
        return row["t"] if row and row["t"] else None

    def posts_in_last_seconds(self, seconds: int, real_only: bool = True) -> int:
        cutoff = int(time.time()) - seconds
        q = "SELECT COUNT(*) AS c FROM posts WHERE posted_at >= ?"
        if real_only:
            q += " AND dry_run = 0"
        cur = self.conn.execute(q, (cutoff,))
        return int(cur.fetchone()["c"])

    def history(self, limit: int = 20) -> list[PostRecord]:
        cur = self.conn.execute(
            "SELECT * FROM posts ORDER BY posted_at DESC LIMIT ?", (limit,)
        )
        return [
            PostRecord(
                id=r["id"],
                article_hash=r["article_hash"],
                article_title=r["article_title"],
                article_url=r["article_url"],
                tweet_text=r["tweet_text"],
                tweet_id=r["tweet_id"],
                posted_at=r["posted_at"],
                dry_run=r["dry_run"],
            )
            for r in cur.fetchall()
        ]
