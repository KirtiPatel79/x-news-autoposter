"""x-news command line interface."""

from __future__ import annotations

import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from .config import load_config
from .generator import GroqGenerator, fallback_generate
from .poster import XPoster
from .scheduler import check_gate
from .selector import mark_articles_seen, select_article
from .sources import fetch_all
from .store import Store, article_hash

console = Console()


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s :: %(message)s",
    )


@click.group()
@click.option("-c", "--config", "config_path", default="config.toml", help="Path to TOML config.")
@click.option("-v", "--verbose", is_flag=True, help="Verbose logs.")
@click.pass_context
def main(ctx: click.Context, config_path: str, verbose: bool) -> None:
    """x-news-autoposter — fetch, generate, and post tech/geopolitics news to X."""
    _setup_logging(verbose)
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config_path


@main.command()
def init() -> None:
    """Copy config.example.toml -> config.toml and .env.example -> .env if missing."""
    root = Path.cwd()
    for src_name, dst_name in [("config.example.toml", "config.toml"), (".env.example", ".env")]:
        src = root / src_name
        dst = root / dst_name
        if not src.exists():
            console.print(f"[yellow]missing[/yellow] {src_name}, skipping")
            continue
        if dst.exists():
            console.print(f"[dim]{dst_name} exists, leaving as-is[/dim]")
            continue
        dst.write_text(src.read_text())
        console.print(f"[green]created[/green] {dst_name}")
    console.print("Done. Edit config.toml and .env, then run [bold]x-news fetch[/bold].")


@main.command()
@click.pass_context
def fetch(ctx: click.Context) -> None:
    """Fetch articles from all configured RSS sources and print a summary."""
    cfg = load_config(ctx.obj["config_path"])
    articles = fetch_all(cfg.sources)
    by_topic: dict[str, int] = {}
    for a in articles:
        by_topic[a.topic] = by_topic.get(a.topic, 0) + 1
    console.print(f"Fetched [bold]{len(articles)}[/bold] articles total")
    for k, v in by_topic.items():
        console.print(f"  {k}: {v}")


@main.command()
@click.option("--dry-run/--no-dry-run", default=None, help="Override config dry_run.")
@click.pass_context
def generate(ctx: click.Context, dry_run: bool | None) -> None:
    """Pick one fresh article and generate a tweet draft (no posting)."""
    cfg = load_config(ctx.obj["config_path"])
    store = Store()
    articles = fetch_all(cfg.sources)
    chosen = select_article(articles, cfg.topics, store)
    if not chosen:
        console.print("[yellow]no fresh articles to post[/yellow]")
        return
    if cfg.secrets.groq_ready():
        gen = GroqGenerator(cfg.secrets, cfg.generator)
        text = gen.generate(chosen)
    else:
        console.print("[yellow]GROQ_API_KEY not set; using fallback generator[/yellow]")
        text = fallback_generate(chosen, cfg.generator)

    console.print(f"[bold]{chosen.source}[/bold] / {chosen.topic}")
    console.print(f"[dim]{chosen.url}[/dim]")
    console.print()
    console.print(text)
    console.print(f"\n[dim]({len(text)} chars)[/dim]")


@main.command("run-once")
@click.option("--dry-run/--no-dry-run", default=None, help="Override config dry_run.")
@click.option(
    "--ignore-gate", is_flag=True, help="Bypass active-hours / min-gap / daily-cap gates."
)
@click.pass_context
def run_once(ctx: click.Context, dry_run: bool | None, ignore_gate: bool) -> None:
    """Full pipeline: fetch -> select -> generate -> post (or dry-run). Intended for cron."""
    cfg = load_config(ctx.obj["config_path"])
    if dry_run is None:
        dry_run = cfg.general.dry_run

    store = Store()

    if not ignore_gate:
        gate = check_gate(cfg.general, store)
        if not gate.allowed:
            console.print(f"[yellow]skipping:[/yellow] {gate.reason}")
            return

    articles = fetch_all(cfg.sources)
    if not articles:
        console.print("[yellow]no articles fetched[/yellow]")
        return

    chosen = select_article(articles, cfg.topics, store)
    if not chosen:
        console.print("[yellow]no fresh articles to post[/yellow]")
        # Still mark seen so we don't keep re-evaluating the same stale set.
        mark_articles_seen(articles, store)
        return

    if cfg.secrets.groq_ready():
        gen = GroqGenerator(cfg.secrets, cfg.generator)
        text = gen.generate(chosen)
    else:
        console.print("[yellow]GROQ_API_KEY not set; using fallback generator[/yellow]")
        text = fallback_generate(chosen, cfg.generator)

    poster = XPoster(cfg.secrets, dry_run=dry_run)
    result = poster.post(text)

    h = article_hash(chosen.url, chosen.title)
    store.mark_seen(h, chosen.title, chosen.url, chosen.topic, chosen.source)
    if result.ok:
        store.record_post(
            article_hash=h,
            title=chosen.title,
            url=chosen.url,
            tweet_text=text,
            tweet_id=result.tweet_id,
            dry_run=result.dry_run,
        )
        if result.dry_run:
            console.print("[green]DRY-RUN ok[/green]")
            console.print(text)
        else:
            console.print(f"[green]posted[/green] tweet {result.tweet_id}")
    else:
        console.print(f"[red]post failed:[/red] {result.error}")
        sys.exit(1)


@main.command()
@click.option("-n", "--limit", default=20, help="How many entries to show.")
def history(limit: int) -> None:
    """Show recent posts."""
    store = Store()
    rows = store.history(limit=limit)
    if not rows:
        console.print("[dim]no posts yet[/dim]")
        return
    table = Table(show_lines=False)
    table.add_column("when (UTC)")
    table.add_column("dry?")
    table.add_column("tweet_id")
    table.add_column("title", overflow="fold")
    for r in rows:
        when = datetime.fromtimestamp(r.posted_at, tz=UTC).strftime("%Y-%m-%d %H:%M")
        table.add_row(
            when,
            "yes" if r.dry_run else "no",
            r.tweet_id or "-",
            r.article_title[:80],
        )
    console.print(table)


if __name__ == "__main__":
    main()
