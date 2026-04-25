from pathlib import Path

from x_news_autoposter.store import Store, article_hash


def test_seen_dedup(tmp_path: Path):
    store = Store(db_path=tmp_path / "s.db")
    h = article_hash("https://example.com/x", "Title")
    assert not store.is_seen(h)
    store.mark_seen(h, "Title", "https://example.com/x", "tech", "Example")
    assert store.is_seen(h)


def test_record_and_history(tmp_path: Path):
    store = Store(db_path=tmp_path / "s.db")
    pid = store.record_post(
        article_hash="h",
        title="Title",
        url="https://example.com/x",
        tweet_text="hi",
        tweet_id="42",
        dry_run=False,
    )
    assert pid > 0
    rows = store.history()
    assert len(rows) == 1
    assert rows[0].tweet_id == "42"
