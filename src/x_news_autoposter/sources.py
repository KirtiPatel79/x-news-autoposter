"""RSS news ingestion."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import feedparser

from .config import Source

log = logging.getLogger(__name__)


@dataclass
class Article:
    title: str
    url: str
    summary: str
    topic: str
    source: str
    published_ts: int  # epoch seconds; 0 if unknown


def _entry_timestamp(entry) -> int:
    for attr in ("published_parsed", "updated_parsed"):
        t = getattr(entry, attr, None) or entry.get(attr) if hasattr(entry, "get") else None
        if t:
            try:
                return int(time.mktime(t))
            except Exception:  # noqa: BLE001
                continue
    return 0


def fetch_source(src: Source, max_items: int = 25) -> list[Article]:
    """Fetch articles from a single RSS source."""
    log.info("fetching %s (%s)", src.name, src.url)
    feed = feedparser.parse(src.url)
    if feed.bozo and not feed.entries:
        log.warning("feed error for %s: %s", src.name, feed.bozo_exception)
        return []
    out: list[Article] = []
    for entry in feed.entries[:max_items]:
        title = (entry.get("title") or "").strip()
        url = (entry.get("link") or "").strip()
        if not title or not url:
            continue
        summary = (entry.get("summary") or entry.get("description") or "").strip()
        out.append(
            Article(
                title=title,
                url=url,
                summary=summary[:1000],
                topic=src.topic,
                source=src.name,
                published_ts=_entry_timestamp(entry),
            )
        )
    log.info("  -> %d articles", len(out))
    return out


def fetch_all(sources: list[Source], max_items_per_source: int = 25) -> list[Article]:
    """Fetch articles from every configured source. Failures are logged and skipped."""
    out: list[Article] = []
    for src in sources:
        try:
            out.extend(fetch_source(src, max_items=max_items_per_source))
        except Exception as e:  # noqa: BLE001
            log.warning("source %s failed: %s", src.name, e)
    return out
