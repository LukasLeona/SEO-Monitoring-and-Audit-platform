from seo_monitor.models import AuditIssue, Severity
from seo_monitor.scoring import calculate_page_score


def test_score_uses_severity_weights_and_never_goes_below_zero() -> None:
    issues = [
        AuditIssue(code=str(index), category="test", severity=Severity.CRITICAL, message="x")
        for index in range(5)
    ]

    assert calculate_page_score(issues) == 0
