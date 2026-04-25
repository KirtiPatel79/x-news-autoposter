"""Tweet generation via Groq."""

from __future__ import annotations

import logging
import re
from urllib.parse import urlparse

from .config import GeneratorCfg, Secrets
from .sources import Article

log = logging.getLogger(__name__)


def _domain(url: str) -> str:
    try:
        host = urlparse(url).netloc
        return host.removeprefix("www.")
    except Exception:  # noqa: BLE001
        return ""


def build_prompt(article: Article, cfg: GeneratorCfg) -> tuple[str, str]:
    """Return (system_prompt, user_prompt)."""
    system = cfg.persona.strip() or (
        "You write concise, informed posts for X about tech and geopolitics."
    )
    user = (
        f"Write ONE post for X about this article. Hard limit: {cfg.max_tweet_chars} characters "
        "INCLUDING the URL (treat the URL as ~25 chars after X's t.co shortener, but keep total under "
        f"{cfg.max_tweet_chars} chars literal). Provide your own short take in plain prose, then the URL "
        "on a new line at the end. Do not use emojis, hashtags, or 'BREAKING:'-style prefixes.\n\n"
        f"Source: {article.source} ({_domain(article.url)})\n"
        f"Title: {article.title}\n"
        f"Summary: {article.summary[:600]}\n"
        f"URL: {article.url}\n"
    )
    return system, user


def _sanitize(text: str) -> str:
    text = text.strip()
    # Strip markdown bold/italics if model adds them.
    text = re.sub(r"\*+", "", text)
    # Strip leading/trailing quotes if model wraps the post.
    if len(text) >= 2 and text[0] in {'"', "'"} and text[-1] == text[0]:
        text = text[1:-1].strip()
    return text


def _truncate_with_url(text: str, url: str, max_chars: int) -> str:
    """Ensure final text is <= max_chars and ends with the URL."""
    if url not in text:
        text = f"{text}\n{url}"
    if len(text) <= max_chars:
        return text

    # Split off the URL, truncate the prose, then re-attach.
    body = text.replace(url, "").rstrip().rstrip("\n").rstrip()
    # Reserve newline + url length.
    budget = max_chars - len(url) - 2
    if budget < 40:
        # Pathological config — just give back the URL.
        return url[:max_chars]
    if len(body) > budget:
        body = body[: budget - 1].rstrip() + "…"
    return f"{body}\n{url}"


class GroqGenerator:
    def __init__(self, secrets: Secrets, cfg: GeneratorCfg):
        if not secrets.groq_ready():
            raise RuntimeError("GROQ_API_KEY not configured")
        # Lazy import so tests / dry-runs without the SDK still pass.
        from groq import Groq  # noqa: PLC0415

        self.client = Groq(api_key=secrets.groq_api_key)
        self.cfg = cfg

    def generate(self, article: Article) -> str:
        system, user = build_prompt(article, self.cfg)
        log.info("calling Groq (%s) for: %s", self.cfg.model, article.title[:80])
        resp = self.client.chat.completions.create(
            model=self.cfg.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=self.cfg.temperature,
            max_tokens=self.cfg.max_tokens,
        )
        text = resp.choices[0].message.content or ""
        text = _sanitize(text)
        text = _truncate_with_url(text, article.url, self.cfg.max_tweet_chars)
        return text


def fallback_generate(article: Article, cfg: GeneratorCfg) -> str:
    """Deterministic fallback when no LLM is available — title + source + url."""
    domain = _domain(article.url) or article.source
    body = f"{article.title} ({domain})"
    return _truncate_with_url(body, article.url, cfg.max_tweet_chars)
