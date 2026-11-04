import httpx
import respx

from seo_monitor.config import Settings
from seo_monitor.fetcher import HTTPFetcher


@respx.mock
async def test_fetcher_retries_transient_status() -> None:
    route = respx.get("https://example.test/").mock(
        side_effect=[
            httpx.Response(503),
            httpx.Response(200, text="<html>ok</html>"),
        ]
    )
    settings = Settings(
        allow_private_hosts=True,
        max_retries=1,
        retry_backoff_seconds=0,
    )

    page = await HTTPFetcher(settings).fetch("https://example.test/")

    assert page.status_code == 200
    assert route.call_count == 2
