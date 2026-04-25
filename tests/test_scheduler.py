import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from x_news_autoposter.config import GeneralCfg
from x_news_autoposter.scheduler import check_gate, in_active_hours
from x_news_autoposter.store import Store


def test_active_hours_basic():
    cfg = GeneralCfg(timezone="UTC", active_hours_start=8, active_hours_end=22)
    tz = ZoneInfo("UTC")
    assert in_active_hours(cfg, datetime(2025, 1, 1, 12, 0, tzinfo=tz)) is True
    assert in_active_hours(cfg, datetime(2025, 1, 1, 23, 0, tzinfo=tz)) is False
    assert in_active_hours(cfg, datetime(2025, 1, 1, 7, 0, tzinfo=tz)) is False


def test_active_hours_wrap():
    # 22:00 -> 06:00
    cfg = GeneralCfg(timezone="UTC", active_hours_start=22, active_hours_end=6)
    tz = ZoneInfo("UTC")
    assert in_active_hours(cfg, datetime(2025, 1, 1, 23, 0, tzinfo=tz)) is True
    assert in_active_hours(cfg, datetime(2025, 1, 1, 3, 0, tzinfo=tz)) is True
    assert in_active_hours(cfg, datetime(2025, 1, 1, 12, 0, tzinfo=tz)) is False


def test_min_gap_blocks(tmp_path: Path):
    store = Store(db_path=tmp_path / "s.db")
    cfg = GeneralCfg(
        timezone="UTC",
        active_hours_start=0,
        active_hours_end=24,
        min_minutes_between_posts=120,
        max_posts_per_day=99,
    )
    # Insert a real post 10 minutes ago.
    store.conn.execute(
        "INSERT INTO posts(article_hash, article_title, article_url, tweet_text, tweet_id, posted_at, dry_run) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("h", "t", "u", "tx", "1", int(time.time()) - 600, 0),
    )
    store.conn.commit()
    g = check_gate(cfg, store)
    assert g.allowed is False
    assert "min-gap" in g.reason


def test_daily_cap_blocks(tmp_path: Path):
    store = Store(db_path=tmp_path / "s.db")
    cfg = GeneralCfg(
        timezone="UTC",
        active_hours_start=0,
        active_hours_end=24,
        min_minutes_between_posts=0,
        max_posts_per_day=1,
    )
    store.conn.execute(
        "INSERT INTO posts(article_hash, article_title, article_url, tweet_text, tweet_id, posted_at, dry_run) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("h", "t", "u", "tx", "1", int(time.time()) - 60, 0),
    )
    store.conn.commit()
    g = check_gate(cfg, store)
    assert g.allowed is False
    assert "daily cap" in g.reason
