# x-news-autoposter

Automated X (Twitter) poster that aggregates **tech** and **geopolitics** news from RSS sources, generates a short post via **Groq**, and posts to your X account on a schedule via **GitHub Actions**.

- Posts to **your own** X account using **your** API credentials (OAuth 1.0a, Read+Write).
- **Dry-run by default** — nothing posts until you flip a config flag and add real secrets.
- Built-in rate limiting: max posts/day, min gap between posts, active-hours window.
- SQLite-backed dedup so the same article never posts twice.
- Pluggable RSS sources, weighted topic mix, keyword include/exclude filters.
- Free to run on GitHub Actions free tier + Groq free tier.

> This tool only posts to accounts **you** own. It does not create accounts and does not bypass any anti-automation system.

## Quick start (local)

```bash
git clone https://github.com/PateLxd/x-news-autoposter.git
cd x-news-autoposter
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
x-news init                   # writes config.toml and .env from examples
# edit config.toml + .env
x-news fetch                  # smoke-test RSS sources
x-news generate               # picks one article and prints a draft tweet
x-news run-once --dry-run     # full pipeline, no posting
x-news run-once --no-dry-run  # actually posts (after secrets are set)
x-news history                # show recent posts
```

## Configuration

### Secrets (`.env` locally / GitHub Actions secrets in production)

| Name | Where to get it |
|------|-----------------|
| `GROQ_API_KEY` | https://console.groq.com/keys |
| `X_CONSUMER_KEY` | X Developer Portal → your app → Keys and tokens → "API Key" |
| `X_CONSUMER_SECRET` | same → "API Key Secret" |
| `X_ACCESS_TOKEN` | same → "Access Token" (must have **Read and Write** permission) |
| `X_ACCESS_TOKEN_SECRET` | same → "Access Token Secret" |

If your app was originally created with Read-only permission, **regenerate the access token after switching to Read+Write** — old tokens keep their old scope.

### `config.toml`

See [`config.example.toml`](./config.example.toml) for the full schema. Highlights:

- `general.timezone` — IANA name (e.g. `Asia/Kolkata`).
- `general.max_posts_per_day` — hard cap (default 6).
- `general.active_hours_start/end` — local-time window when posting is allowed (default 7–23).
- `general.min_minutes_between_posts` — minimum gap between real posts (default 120).
- `general.dry_run` — when true, all `run-once` invocations log but never post. Default: **true**.
- `generator.model` — Groq model (default `llama-3.3-70b-versatile`).
- `generator.persona` — the voice prompt baked into every generation.
- `topics.tech` / `topics.geopolitics` — weights for sampling which topic to post next.
- `[[sources]]` — list of RSS feeds with their topic.

### Topic balance

Default config has `tech = 1.0` and `geopolitics = 1.0` — a 50/50 mix, weighted random per run. Adjust as you like; weights are relative, not percentages.

## Running on GitHub Actions

Workflow: [`.github/workflows/post.yml`](./.github/workflows/post.yml). Cron fires every 2 hours; the app's own gate skips runs that fall outside active hours, hit the daily cap, or are too close to the previous post.

### Setup

1. Push this repo to your GitHub account (public or private — public is fine, no secrets are committed).
2. Settings → Secrets and variables → Actions → "New repository secret". Add: `GROQ_API_KEY`, `X_CONSUMER_KEY`, `X_CONSUMER_SECRET`, `X_ACCESS_TOKEN`, `X_ACCESS_TOKEN_SECRET`.
3. Edit `config.toml` and set `dry_run = false` once you're confident.
4. The workflow auto-commits `data/state.db` back to the repo so dedup state survives runs. Make sure the repo allows the default `GITHUB_TOKEN` to push (Settings → Actions → General → Workflow permissions → "Read and write permissions"). State is also cached as a fallback.
5. Manually kick off the first run from the Actions tab → "Post to X" → "Run workflow" with `dry_run=true` to verify generation, then again with `dry_run=false`.

### Privacy / cost note

- All commits to `data/state.db` contain titles, URLs, and tweet text only — never your API keys.
- GitHub Actions free tier: 2000 minutes/month for public repos is unlimited. This job runs in <30s.
- Groq free tier is generous; `llama-3.3-70b-versatile` is well within limits at 6 calls/day.

## Development

```bash
pip install -e ".[dev]"
ruff check .
pytest
```

## How posts are generated

For each scheduled run, the app:

1. Skips the run if outside active hours, daily cap reached, or last post was too recent.
2. Fetches all configured RSS feeds.
3. Filters out anything matching `must_exclude_any` and (if set) requires `must_include_any`.
4. Filters out articles already seen.
5. Buckets by topic, picks a topic by weight, picks one of the top-5 freshest in that bucket.
6. Generates a tweet via Groq using the configured `persona`. Output is sanitized and hard-truncated to fit `max_tweet_chars` (default 275, leaving headroom for X's t.co shortener).
7. Posts via `tweepy` and records the result in SQLite.

## License

MIT.
