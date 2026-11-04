from collections import Counter

from seo_monitor.models import AuditComparison, AuditReport, Severity


def compare_audits(
    baseline: AuditReport,
    current: AuditReport,
) -> AuditComparison:
    baseline_codes = {issue.code for page in baseline.pages for issue in page.issues}
    current_codes = {issue.code for page in current.pages for issue in page.issues}
    baseline_counts = Counter(issue.severity for page in baseline.pages for issue in page.issues)
    current_counts = Counter(issue.severity for page in current.pages for issue in page.issues)

    return AuditComparison(
        baseline_id=baseline.id,
        current_id=current.id,
        score_change=current.score - baseline.score,
        pages_change=current.pages_scanned - baseline.pages_scanned,
        issue_changes={
            severity: current_counts[severity] - baseline_counts[severity] for severity in Severity
        },
        new_issue_codes=sorted(current_codes - baseline_codes),
        resolved_issue_codes=sorted(baseline_codes - current_codes),
    )
