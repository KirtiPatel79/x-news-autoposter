"""X (Twitter) posting via tweepy v2."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from .config import Secrets

log = logging.getLogger(__name__)


@dataclass
class PostResult:
    ok: bool
    tweet_id: str | None
    error: str | None
    dry_run: bool


class XPoster:
    def __init__(self, secrets: Secrets, dry_run: bool = True):
        self.dry_run = dry_run
        self.secrets = secrets
        self._client = None
        if not dry_run:
            if not secrets.x_ready():
                raise RuntimeError(
                    "X API credentials are missing. Set X_CONSUMER_KEY/SECRET and X_ACCESS_TOKEN/SECRET."
                )
            import tweepy  # noqa: PLC0415

            self._client = tweepy.Client(
                consumer_key=secrets.x_consumer_key,
                consumer_secret=secrets.x_consumer_secret,
                access_token=secrets.x_access_token,
                access_token_secret=secrets.x_access_token_secret,
            )

    def post(self, text: str) -> PostResult:
        if self.dry_run:
            log.info("[DRY-RUN] would post:\n%s", text)
            return PostResult(ok=True, tweet_id=None, error=None, dry_run=True)
        try:
            assert self._client is not None
            resp = self._client.create_tweet(text=text)
            tweet_id = str(resp.data["id"]) if resp and resp.data else None
            log.info("posted tweet %s", tweet_id)
            return PostResult(ok=True, tweet_id=tweet_id, error=None, dry_run=False)
        except Exception as e:  # noqa: BLE001
            log.error("post failed: %s", e)
            return PostResult(ok=False, tweet_id=None, error=str(e), dry_run=False)
