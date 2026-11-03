from dataclasses import dataclass
from time import perf_counter
from urllib.parse import urljoin

import httpx

from seo_monitor.config import Settings
from seo_monitor.security import validate_public_url


class FetchError(RuntimeError):
    pass


@dataclass(slots=True)
class FetchedPage:
    requested_url: str
    final_url: str
    status_code: int
    headers: dict[str, str]
    html: str
    duration_ms: int

    @property
    def content_type(self) -> str | None:
        return self.headers.get("content-type")


class HTTPFetcher:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def fetch(self, url: str) -> FetchedPage:
        requested_url = await validate_public_url(
            url,
            allow_private_hosts=self.settings.allow_private_hosts,
        )
        current_url = requested_url
        started = perf_counter()

        timeout = httpx.Timeout(self.settings.request_timeout_seconds)
        headers = {
            "User-Agent": self.settings.user_agent,
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.1",
        }
        async with httpx.AsyncClient(
            timeout=timeout,
            headers=headers,
            follow_redirects=False,
            trust_env=False,
        ) as client:
            for _ in range(6):
                try:
                    async with client.stream("GET", current_url) as response:
                        if response.is_redirect:
                            location = response.headers.get("location")
                            if not location:
                                raise FetchError("redirect response did not include a location")
                            current_url = await validate_public_url(
                                urljoin(current_url, location),
                                allow_private_hosts=self.settings.allow_private_hosts,
                            )
                            continue

                        body = bytearray()
                        async for chunk in response.aiter_bytes():
                            body.extend(chunk)
                            if len(body) > self.settings.max_response_bytes:
                                raise FetchError("response exceeded the configured size limit")

                        encoding = response.encoding or "utf-8"
                        html = bytes(body).decode(encoding, errors="replace")
                        return FetchedPage(
                            requested_url=requested_url,
                            final_url=str(response.url),
                            status_code=response.status_code,
                            headers={key.lower(): value for key, value in response.headers.items()},
                            html=html,
                            duration_ms=round((perf_counter() - started) * 1000),
                        )
                except httpx.HTTPError as exc:
                    raise FetchError(f"request failed: {exc}") from exc

        raise FetchError("too many redirects")
