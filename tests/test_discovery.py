from seo_monitor.config import Settings
from seo_monitor.fetcher import FetchedPage, HTTPFetcher
from seo_monitor.robots import RobotsPolicy
from seo_monitor.sitemap import SitemapLoader


def response(url: str, body: str, status: int = 200) -> FetchedPage:
    return FetchedPage(
        requested_url=url,
        final_url=url,
        status_code=status,
        headers={"content-type": "text/plain"},
        html=body,
        duration_ms=1,
    )


async def test_robots_policy_parses_rules_delay_and_sitemap(monkeypatch) -> None:
    async def fake_fetch(self, url: str) -> FetchedPage:
        return response(
            url,
            """
            User-agent: SEOMonitorBot
            Disallow: /private
            Crawl-delay: 2
            Sitemap: https://example.test/sitemap.xml
            """,
        )

    monkeypatch.setattr(HTTPFetcher, "fetch", fake_fetch)
    policy = await RobotsPolicy.load(
        "https://example.test/",
        Settings(allow_private_hosts=True),
    )

    assert policy.can_fetch("https://example.test/public")
    assert not policy.can_fetch("https://example.test/private")
    assert policy.crawl_delay == 2
    assert policy.sitemaps == ["https://example.test/sitemap.xml"]


async def test_sitemap_loader_reads_same_origin_urls() -> None:
    class StubFetcher:
        requested_urls: list[str] = []

        async def fetch(self, url: str) -> FetchedPage:
            self.requested_urls.append(url)
            return response(
                url,
                """
                <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
                  <url><loc>https://example.test/one</loc></url>
                  <url><loc>https://other.test/outside</loc></url>
                </urlset>
                """,
            )

    loader = SitemapLoader(Settings(allow_private_hosts=True))
    loader.fetcher = StubFetcher()

    urls = await loader.discover(
        "https://example.test/",
        ["https://example.test/sitemap.xml"],
        max_urls=10,
    )

    assert urls == ["https://example.test/one"]


async def test_sitemap_fallback_uses_origin_root() -> None:
    class StubFetcher:
        requested_url = ""

        async def fetch(self, url: str) -> FetchedPage:
            self.requested_url = url
            return response(url, "<urlset />")

    loader = SitemapLoader(Settings(allow_private_hosts=True))
    fetcher = StubFetcher()
    loader.fetcher = fetcher

    await loader.discover(
        "https://example.test/nested/page",
        [],
        max_urls=10,
    )

    assert fetcher.requested_url == "https://example.test/sitemap.xml"
