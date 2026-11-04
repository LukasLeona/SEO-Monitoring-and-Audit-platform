import csv
import io
from collections import Counter

from seo_monitor.models import AuditReport, Severity


def audit_to_csv(report: AuditReport) -> str:
    output = io.StringIO(newline="")
    fieldnames = [
        "audit_id",
        "url",
        "status_code",
        "score",
        "title",
        "meta_description",
        "word_count",
        "internal_links",
        "external_links",
        "critical_issues",
        "error_issues",
        "warning_issues",
        "info_issues",
        "issue_codes",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()

    for page in report.pages:
        counts = Counter(issue.severity for issue in page.issues)
        writer.writerow(
            {
                "audit_id": report.id,
                "url": page.final_url,
                "status_code": page.status_code,
                "score": page.score,
                "title": page.title or "",
                "meta_description": page.meta_description or "",
                "word_count": page.word_count,
                "internal_links": page.internal_links,
                "external_links": page.external_links,
                "critical_issues": counts[Severity.CRITICAL],
                "error_issues": counts[Severity.ERROR],
                "warning_issues": counts[Severity.WARNING],
                "info_issues": counts[Severity.INFO],
                "issue_codes": "|".join(issue.code for issue in page.issues),
            }
        )

    return output.getvalue()
