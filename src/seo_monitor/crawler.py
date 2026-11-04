import asyncio
from collections import deque
from typing import Protocol

from seo_monitor.analyzer import analyze_page
from seo_monitor.config import Settings
from seo_monitor.fetcher import FetchedPage
from seo_monitor.models import AuditIssue, PageAudit, Severity
from seo_monitor.robots import RobotsPolicy
from seo_monitor.scoring import score_page
from seo_monitor.security import normalize_url
from seo_monitor.sitemap import SitemapLoader


class PageFetcher(Protocol):
    async def fetch(self, url: str) -> FetchedPage: ...


class Crawler:
    def __init__(self, fetcher: PageFetcher, settings: Settings) -> None:
        self.fetcher = fetcher
        self.settings = settings

    async def crawl(
        self,
        root_url: str,
        *,
        max_pages: int,
        respect_robots: bool = True,
        use_sitemap: bool = False,
    ) -> list[PageAudit]:
        limit = min(max_pages, self.settings.max_crawl_pages)
        queue: deque[str] = deque([normalize_url(root_url)])
        seen: set[str] = set()
        pages: list[PageAudit] = []
        robots = await RobotsPolicy.load(root_url, self.settings) if respect_robots else None
        if use_sitemap and limit > 1:
            sitemap_urls = await SitemapLoader(self.settings).discover(
                root_url,
                robots.sitemaps if robots else [],
                max_urls=limit - 1,
            )
            queue.extend(sitemap_urls)
        first_batch = True

        while queue and len(seen) < limit:
            batch: list[str] = []
            concurrency = 1 if robots and robots.crawl_delay else self.settings.crawl_concurrency
            while queue and len(batch) < concurrency and len(seen) < limit:
                url = queue.popleft()
                if url in seen:
                    continue
                seen.add(url)
                if robots and not robots.can_fetch(url):
                    pages.append(
                        PageAudit(
                            url=url,
                            final_url=url,
                            status_code=0,
                            score=100,
                            issues=[
                                AuditIssue(
                                    code="robots.disallowed",
                                    category="crawlability",
                                    severity=Severity.INFO,
                                    message="Page is disallowed by robots.txt",
                                )
                            ],
                        )
                    )
                    continue
                batch.append(url)

            if not batch:
                continue
            if robots and robots.crawl_delay and not first_batch:
                await asyncio.sleep(robots.crawl_delay)
            first_batch = False
            outcomes = await asyncio.gather(
                *(self.fetcher.fetch(url) for url in batch),
                return_exceptions=True,
            )
            for url, outcome in zip(batch, outcomes, strict=True):
                if isinstance(outcome, BaseException):
                    failed = PageAudit(
                        url=url,
                        final_url=url,
                        status_code=0,
                        score=0,
                        issues=[
                            AuditIssue(
                                code="fetch.failed",
                                category="availability",
                                severity=Severity.CRITICAL,
                                message="Page could not be fetched",
                                evidence={"error": str(outcome)},
                            )
                        ],
                    )
                    pages.append(failed)
                    continue

                analysis = analyze_page(outcome)
                pages.append(score_page(analysis.audit))
                for link in analysis.discovered_links:
                    if link not in seen:
                        queue.append(link)

        return pages
