from seo_monitor.config import Settings
from seo_monitor.crawler import Crawler
from seo_monitor.fetcher import FetchedPage


class StubFetcher:
    async def fetch(self, url: str) -> FetchedPage:
        path = url.rstrip("/").rsplit("/", 1)[-1]
        next_link = '<a href="/second">next</a>' if path == "example.test" else ""
        return FetchedPage(
            requested_url=url,
            final_url=url,
            status_code=200,
            headers={"content-type": "text/html"},
            html=(
                "<html lang='en'><title>A useful page title for testing</title>"
                f"<h1>Page</h1>{next_link}</html>"
            ),
            duration_ms=1,
        )


async def test_crawler_follows_internal_links_within_limit() -> None:
    settings = Settings(allow_private_hosts=True, crawl_concurrency=2)
    pages = await Crawler(StubFetcher(), settings).crawl(
        "https://example.test",
        max_pages=2,
    )

    assert [page.final_url for page in pages] == [
        "https://example.test/",
        "https://example.test/second",
    ]
