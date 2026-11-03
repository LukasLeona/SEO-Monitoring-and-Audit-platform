from collections import Counter

from seo_monitor.models import AuditIssue, PageAudit, Severity

DEDUCTIONS: dict[Severity, int] = {
    Severity.CRITICAL: 30,
    Severity.ERROR: 15,
    Severity.WARNING: 5,
    Severity.INFO: 1,
}


def calculate_page_score(issues: list[AuditIssue]) -> int:
    deduction = sum(DEDUCTIONS[issue.severity] for issue in issues)
    return max(0, min(100, 100 - deduction))


def score_page(page: PageAudit) -> PageAudit:
    return page.model_copy(update={"score": calculate_page_score(page.issues)})


def calculate_report_score(pages: list[PageAudit]) -> int:
    if not pages:
        return 0
    return round(sum(page.score for page in pages) / len(pages))


def summarize_issues(pages: list[PageAudit]) -> dict[Severity, int]:
    counts = Counter(issue.severity for page in pages for issue in page.issues)
    return {severity: counts.get(severity, 0) for severity in Severity}

