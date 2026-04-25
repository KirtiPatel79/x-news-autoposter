"""Article selection: filter, dedup, weight by topic, pick the best candidate."""

from __future__ import annotations

import random
import time

from .config import TopicsCfg
from .sources import Article
from .store import Store, article_hash


def _passes_filters(a: Article, topics: TopicsCfg) -> bool:
    title_l = a.title.lower()
    if topics.must_include_any and not any(
        k.lower() in title_l for k in topics.must_include_any
    ):
        return False
    return not (
        topics.must_exclude_any
        and any(k.lower() in title_l for k in topics.must_exclude_any)
    )


def filter_unseen(articles: list[Article], store: Store) -> list[Article]:
    out = []
    for a in articles:
        h = article_hash(a.url, a.title)
        if not store.is_seen(h):
            out.append(a)
    return out


def select_article(
    articles: list[Article],
    topics: TopicsCfg,
    store: Store,
    rng: random.Random | None = None,
) -> Article | None:
    """Pick one article to post next.

    Strategy: filter -> dedup -> bucket by topic -> pick a topic by weight ->
    pick the most recent article in that topic.
    """
    rng = rng or random.Random()

    candidates = [a for a in articles if _passes_filters(a, topics)]
    candidates = filter_unseen(candidates, store)
    if not candidates:
        return None

    weights: dict[str, float] = {
        "tech": max(0.0, topics.tech),
        "geopolitics": max(0.0, topics.geopolitics),
    }

    buckets: dict[str, list[Article]] = {k: [] for k in weights}
    for a in candidates:
        if a.topic in buckets:
            buckets[a.topic].append(a)

    available = [(t, w) for t, w in weights.items() if w > 0 and buckets[t]]
    if not available:
        return None

    topics_list = [t for t, _ in available]
    weights_list = [w for _, w in available]
    chosen_topic = rng.choices(topics_list, weights=weights_list, k=1)[0]

    bucket = buckets[chosen_topic]
    bucket.sort(key=lambda a: a.published_ts or 0, reverse=True)
    # Slight randomness within the top-5 freshest so we don't always pick the literal newest.
    top = bucket[:5]
    return rng.choice(top) if top else None


def mark_articles_seen(articles: list[Article], store: Store) -> None:
    for a in articles:
        h = article_hash(a.url, a.title)
        store.mark_seen(h, a.title, a.url, a.topic, a.source)


def now_ts() -> int:
    return int(time.time())
