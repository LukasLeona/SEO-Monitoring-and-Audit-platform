import asyncio
from collections import deque
from typing import Protocol

from seo_monitor.analyzer import analyze_page
from seo_monitor.config import Settings
from seo_monitor.fetcher import FetchedPage
from seo_monitor.models import AuditIssue, PageAudit, Severity
from seo_monitor.scoring import score_page
from seo_monitor.security import normalize_url


class PageFetcher(Protocol):
    async def fetch(self, url: str) -> FetchedPage: ...


class Crawler:
    def __init__(self, fetcher: PageFetcher, settings: Settings) -> None:
        self.fetcher = fetcher
        self.settings = settings

    async def crawl(self, root_url: str, *, max_pages: int) -> list[PageAudit]:
        limit = min(max_pages, self.settings.max_crawl_pages)
        queue: deque[str] = deque([normalize_url(root_url)])
        seen: set[str] = set()
        pages: list[PageAudit] = []

        while queue and len(seen) < limit:
            batch: list[str] = []
            while queue and len(batch) < self.settings.crawl_concurrency and len(seen) < limit:
                url = queue.popleft()
                if url in seen:
                    continue
                seen.add(url)
                batch.append(url)

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
