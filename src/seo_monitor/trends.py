from seo_monitor.models import AuditReport, AuditTrend, AuditTrendPoint


def build_trend(root_url: str, reports: list[AuditReport]) -> AuditTrend:
    return AuditTrend(
        root_url=root_url,
        points=[
            AuditTrendPoint(
                audit_id=report.id,
                completed_at=report.completed_at,
                score=report.score,
                pages_scanned=report.pages_scanned,
                issue_summary=report.issue_summary,
            )
            for report in reports
        ],
    )
