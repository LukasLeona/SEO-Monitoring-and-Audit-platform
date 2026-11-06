from collections import Counter, defaultdict

from seo_monitor.models import (
    AuditInsights,
    AuditReport,
    InsightIssue,
    Severity,
    SlowPage,
)

SEVERITY_ORDER = {
    Severity.CRITICAL: 4,
    Severity.ERROR: 3,
    Severity.WARNING: 2,
    Severity.INFO: 1,
}


def _grade(score: int) -> str:
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


def build_insights(report: AuditReport) -> AuditInsights:
    issue_counts: Counter[str] = Counter()
    categories: Counter[str] = Counter()
    affected_pages: dict[str, set[str]] = defaultdict(set)
    issue_examples = {}

    for page in report.pages:
        for issue in page.issues:
            issue_counts[issue.code] += 1
            categories[issue.category] += 1
            affected_pages[issue.code].add(page.final_url)
            issue_examples.setdefault(issue.code, issue)

    top_issues = [
        InsightIssue(
            code=code,
            category=issue_examples[code].category,
            severity=issue_examples[code].severity,
            occurrences=count,
            affected_pages=sorted(affected_pages[code]),
            remediation=issue_examples[code].remediation,
        )
        for code, count in issue_counts.items()
    ]
    top_issues.sort(
        key=lambda item: (
            -SEVERITY_ORDER[item.severity],
            -item.occurrences,
            item.code,
        )
    )

    indexable_pages = sum(
        1
        for page in report.pages
        if 200 <= page.status_code < 300 and "noindex" not in (page.meta_robots or "").lower()
    )
    slowest_pages = [
        SlowPage(
            url=page.final_url,
            duration_ms=page.duration_ms,
            status_code=page.status_code,
        )
        for page in sorted(
            report.pages,
            key=lambda page: page.duration_ms,
            reverse=True,
        )[:10]
    ]

    return AuditInsights(
        audit_id=report.id,
        score=report.score,
        grade=_grade(report.score),
        total_issues=sum(issue_counts.values()),
        indexable_pages=indexable_pages,
        category_totals=dict(sorted(categories.items())),
        top_issues=top_issues[:10],
        slowest_pages=slowest_pages,
    )
