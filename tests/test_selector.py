import random
from pathlib import Path

from x_news_autoposter.config import TopicsCfg
from x_news_autoposter.selector import select_article
from x_news_autoposter.sources import Article
from x_news_autoposter.store import Store


def _make(title: str, topic: str, ts: int = 0) -> Article:
    return Article(
        title=title,
        url=f"https://example.com/{title.replace(' ', '-').lower()}",
        summary="",
        topic=topic,
        source="Example",
        published_ts=ts,
    )


def test_select_prefers_unseen(tmp_path: Path):
    store = Store(db_path=tmp_path / "s.db")
    arts = [_make("a", "tech", 100), _make("b", "geopolitics", 200)]
    rng = random.Random(0)
    chosen = select_article(arts, TopicsCfg(), store, rng=rng)
    assert chosen is not None


def test_must_exclude(tmp_path: Path):
    store = Store(db_path=tmp_path / "s.db")
    arts = [_make("Sponsored thing", "tech", 100)]
    chosen = select_article(arts, TopicsCfg(must_exclude_any=["sponsored"]), store)
    assert chosen is None


def test_must_include(tmp_path: Path):
    store = Store(db_path=tmp_path / "s.db")
    arts = [_make("AI breakthrough", "tech", 100), _make("random news", "tech", 200)]
    chosen = select_article(arts, TopicsCfg(must_include_any=["ai"]), store)
    assert chosen is not None
    assert "AI" in chosen.title
