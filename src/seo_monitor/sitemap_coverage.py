from seo_monitor.models import AuditReport, SitemapCoverage, SitemapPageStatus


def build_sitemap_coverage(report: AuditReport) -> SitemapCoverage:
    sitemap_pages = [page for page in report.pages if page.discovered_from == "sitemap"]
    page_statuses = [
        SitemapPageStatus(
            url=page.final_url,
            status_code=page.status_code,
            score=page.score,
            orphaned=any(issue.code == "sitewide.orphan_page" for issue in page.issues),
        )
        for page in sitemap_pages
    ]
    return SitemapCoverage(
        audit_id=report.id,
        sampled_urls=len(page_statuses),
        healthy_urls=sum(1 for page in page_statuses if 200 <= page.status_code < 300),
        error_urls=sum(
            1 for page in page_statuses if page.status_code == 0 or page.status_code >= 400
        ),
        orphaned_urls=sum(1 for page in page_statuses if page.orphaned),
        pages=page_statuses,
    )
