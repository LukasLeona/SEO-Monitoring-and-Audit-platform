from datetime import UTC, datetime
from uuid import uuid4

from seo_monitor.browser import BrowserFetcher
from seo_monitor.config import Settings
from seo_monitor.crawler import Crawler
from seo_monitor.fetcher import HTTPFetcher
from seo_monitor.models import AuditReport, AuditRequest
from seo_monitor.repository import AuditRepository
from seo_monitor.scoring import calculate_report_score, summarize_issues


class AuditService:
    def __init__(self, settings: Settings, repository: AuditRepository) -> None:
        self.settings = settings
        self.repository = repository

    async def run(self, request: AuditRequest) -> AuditReport:
        started_at = datetime.now(UTC)
        root_url = str(request.url)

        if request.use_browser:
            async with BrowserFetcher(self.settings) as fetcher:
                pages = await Crawler(fetcher, self.settings).crawl(
                    root_url,
                    max_pages=request.max_pages,
                )
        else:
            fetcher = HTTPFetcher(self.settings)
            pages = await Crawler(fetcher, self.settings).crawl(
                root_url,
                max_pages=request.max_pages,
            )

        report = AuditReport(
            id=str(uuid4()),
            root_url=root_url,
            started_at=started_at,
            completed_at=datetime.now(UTC),
            score=calculate_report_score(pages),
            pages_scanned=len(pages),
            issue_summary=summarize_issues(pages),
            pages=pages,
        )
        await self.repository.save(report)
        return report
