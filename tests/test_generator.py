from x_news_autoposter.config import GeneratorCfg
from x_news_autoposter.generator import _truncate_with_url, fallback_generate
from x_news_autoposter.sources import Article


def test_truncate_keeps_url():
    body = "x" * 500
    url = "https://example.com/a"
    out = _truncate_with_url(body, url, 275)
    assert url in out
    assert len(out) <= 275
    assert out.endswith(url)


def test_truncate_short_body_unchanged():
    body = "Short take here."
    url = "https://example.com/a"
    out = _truncate_with_url(body, url, 275)
    assert body in out
    assert out.endswith(url)


def test_fallback_generate_under_limit():
    a = Article(
        title="A long title " * 30,
        url="https://example.com/article",
        summary="",
        topic="tech",
        source="Example",
        published_ts=0,
    )
    cfg = GeneratorCfg(max_tweet_chars=275)
    out = fallback_generate(a, cfg)
    assert len(out) <= 275
    assert a.url in out
