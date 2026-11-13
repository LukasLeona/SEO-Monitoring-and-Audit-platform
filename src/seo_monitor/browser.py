from time import perf_counter

from playwright.async_api import Browser, Playwright, Route, async_playwright

from seo_monitor.config import Settings
from seo_monitor.fetcher import FetchedPage, FetchError
from seo_monitor.security import UnsafeURLError, validate_public_url


class BrowserFetcher:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None

    async def __aenter__(self) -> "BrowserFetcher":
        try:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=True)
        except Exception as exc:
            await self.close()
            raise FetchError(
                "Chromium could not start; run 'uv run playwright install chromium'"
            ) from exc
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    async def close(self) -> None:
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    async def fetch(self, url: str) -> FetchedPage:
        if not self._browser:
            raise FetchError("BrowserFetcher must be used as an async context manager")

        requested_url = await validate_public_url(
            url,
            allow_private_hosts=self.settings.allow_private_hosts,
        )
        context = await self._browser.new_context(user_agent=self.settings.user_agent)
        page = await context.new_page()

        async def guard_request(route: Route) -> None:
            try:
                await validate_public_url(
                    route.request.url,
                    allow_private_hosts=self.settings.allow_private_hosts,
                )
                await route.continue_()
            except (UnsafeURLError, ValueError):
                await route.abort("blockedbyclient")

        await page.route("**/*", guard_request)
        started = perf_counter()
        try:
            response = await page.goto(
                requested_url,
                wait_until="domcontentloaded",
                timeout=self.settings.request_timeout_seconds * 1000,
            )
            if response is None:
                raise FetchError("browser navigation returned no response")
            final_url = await validate_public_url(
                page.url,
                allow_private_hosts=self.settings.allow_private_hosts,
            )
            html = await page.content()
            if len(html.encode("utf-8")) > self.settings.max_response_bytes:
                raise FetchError("rendered page exceeded the configured size limit")
            headers = {key.lower(): value for key, value in (await response.all_headers()).items()}
            return FetchedPage(
                requested_url=requested_url,
                final_url=final_url,
                status_code=response.status,
                headers=headers,
                html=html,
                duration_ms=round((perf_counter() - started) * 1000),
                redirect_chain=(
                    [requested_url, final_url] if requested_url != final_url else [requested_url]
                ),
            )
        except FetchError:
            raise
        except Exception as exc:
            raise FetchError(f"browser request failed: {exc}") from exc
        finally:
            await context.close()
