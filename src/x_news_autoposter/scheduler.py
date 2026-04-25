"""Decisions about whether it's time to post."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from .config import GeneralCfg
from .store import Store

log = logging.getLogger(__name__)


@dataclass
class Gate:
    allowed: bool
    reason: str


def in_active_hours(cfg: GeneralCfg, now: datetime | None = None) -> bool:
    tz = ZoneInfo(cfg.timezone)
    now = now or datetime.now(tz)
    local = now.astimezone(tz)
    h = local.hour
    start = cfg.active_hours_start
    end = cfg.active_hours_end
    if start <= end:
        return start <= h < end
    # Wrap-around (e.g. 22..6) — treat as: h >= start OR h < end.
    return h >= start or h < end


def check_gate(cfg: GeneralCfg, store: Store, now: datetime | None = None) -> Gate:
    """Decide whether posting is allowed right now."""
    tz = ZoneInfo(cfg.timezone)
    now = now or datetime.now(tz)

    if not in_active_hours(cfg, now):
        return Gate(False, f"outside active hours ({cfg.active_hours_start}-{cfg.active_hours_end})")

    # Day cap (use local-day boundary).
    local = now.astimezone(tz)
    start_of_day = local.replace(hour=0, minute=0, second=0, microsecond=0)
    seconds_into_day = int((local - start_of_day).total_seconds())
    posts_today = store.posts_in_last_seconds(seconds_into_day, real_only=True)
    if posts_today >= cfg.max_posts_per_day:
        return Gate(False, f"daily cap reached ({posts_today}/{cfg.max_posts_per_day})")

    # Min gap.
    last = store.last_post_time(real_only=True)
    if last is not None:
        gap_required = cfg.min_minutes_between_posts * 60
        elapsed = int(now.timestamp()) - last
        if elapsed < gap_required:
            mins = (gap_required - elapsed) // 60
            return Gate(False, f"min-gap not met (~{mins} min remaining)")

    return Gate(True, "ok")
