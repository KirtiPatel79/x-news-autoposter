"""Config loading from TOML + environment variables."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


@dataclass
class Source:
    name: str
    url: str
    topic: str


@dataclass
class GeneralCfg:
    timezone: str = "UTC"
    max_posts_per_day: int = 6
    active_hours_start: int = 7
    active_hours_end: int = 23
    min_minutes_between_posts: int = 120
    jitter_seconds: int = 180
    dry_run: bool = True


@dataclass
class GeneratorCfg:
    model: str = "llama-3.3-70b-versatile"
    temperature: float = 0.7
    max_tokens: int = 200
    persona: str = ""
    max_tweet_chars: int = 275


@dataclass
class TopicsCfg:
    tech: float = 1.0
    geopolitics: float = 1.0
    must_include_any: list[str] = field(default_factory=list)
    must_exclude_any: list[str] = field(default_factory=list)


@dataclass
class Secrets:
    groq_api_key: str = ""
    x_consumer_key: str = ""
    x_consumer_secret: str = ""
    x_access_token: str = ""
    x_access_token_secret: str = ""

    def x_ready(self) -> bool:
        return all(
            [
                self.x_consumer_key,
                self.x_consumer_secret,
                self.x_access_token,
                self.x_access_token_secret,
            ]
        )

    def groq_ready(self) -> bool:
        return bool(self.groq_api_key)


@dataclass
class Config:
    general: GeneralCfg
    generator: GeneratorCfg
    topics: TopicsCfg
    sources: list[Source]
    secrets: Secrets


def load_config(config_path: str | Path = "config.toml") -> Config:
    """Load config from a TOML file and secrets from .env / environment."""
    load_dotenv()
    p = Path(config_path)
    if not p.exists():
        # Fall back to example so tests / first-time users don't crash.
        example = Path(__file__).resolve().parents[2] / "config.example.toml"
        if example.exists():
            p = example
        else:
            raise FileNotFoundError(f"Config not found: {config_path}")

    data = tomllib.loads(p.read_text())

    general = GeneralCfg(**data.get("general", {}))
    generator = GeneratorCfg(**data.get("generator", {}))
    topics = TopicsCfg(**data.get("topics", {}))
    sources = [Source(**s) for s in data.get("sources", [])]

    secrets = Secrets(
        groq_api_key=os.environ.get("GROQ_API_KEY", ""),
        x_consumer_key=os.environ.get("X_CONSUMER_KEY", ""),
        x_consumer_secret=os.environ.get("X_CONSUMER_SECRET", ""),
        x_access_token=os.environ.get("X_ACCESS_TOKEN", ""),
        x_access_token_secret=os.environ.get("X_ACCESS_TOKEN_SECRET", ""),
    )

    return Config(
        general=general,
        generator=generator,
        topics=topics,
        sources=sources,
        secrets=secrets,
    )
