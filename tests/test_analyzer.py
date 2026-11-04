from seo_monitor.analyzer import analyze_page
from seo_monitor.fetcher import FetchedPage


def test_analyzer_extracts_signals_and_issues() -> None:
    page = FetchedPage(
        requested_url="https://example.com/",
        final_url="https://example.com/",
        status_code=200,
        headers={"content-type": "text/html; charset=utf-8"},
        html="""
        <html><head><title>Short</title>
        <meta name="viewport" content="width=device-width">
        <meta property="og:title" content="Short">
        <meta name="twitter:card" content="summary">
        <script type="application/ld+json">{"@type":"WebPage"}</script>
        </head>
        <body><h1>Welcome</h1><img src="/hero.png">
        <a href="/about">About</a><a href="https://other.test">Other</a>
        </body></html>
        """,
        duration_ms=12,
    )

    result = analyze_page(page)
    codes = {issue.code for issue in result.audit.issues}

    assert result.audit.title == "Short"
    assert result.audit.internal_links == 1
    assert result.audit.external_links == 1
    assert result.audit.images_without_alt == 1
    assert result.audit.has_viewport
    assert result.audit.has_open_graph
    assert result.audit.has_twitter_card
    assert result.audit.structured_data_types == ["WebPage"]
    assert result.discovered_links == ["https://example.com/about"]
    assert {"title.short", "description.missing", "image.alt_missing"} <= codes
