import csv
import io
import json
from datetime import UTC, datetime

from seo_monitor.comparison import compare_audits
from seo_monitor.exporter import audit_to_csv, audit_to_jsonl
from seo_monitor.insights import build_insights
from seo_monitor.models import AuditIssue, AuditReport, PageAudit, Severity
from seo_monitor.sitemap_coverage import build_sitemap_coverage
from seo_monitor.sitewide import apply_sitewide_checks
from seo_monitor.trends import build_trend


def report(report_id: str, score: int, pages: list[PageAudit]) -> AuditReport:
    now = datetime.now(UTC)
    return AuditReport(
        id=report_id,
        root_url="https://example.test/",
        started_at=now,
        completed_at=now,
        score=score,
        pages_scanned=len(pages),
        issue_summary={severity: 0 for severity in Severity},
        pages=pages,
    )


def test_sitewide_checks_flag_duplicate_titles_and_descriptions() -> None:
    pages = [
        PageAudit(
            url=f"https://example.test/{index}",
            final_url=f"https://example.test/{index}",
            status_code=200,
            title="Duplicate",
            meta_description="The same description",
        )
        for index in range(2)
    ]

    checked = apply_sitewide_checks(pages)

    assert all(
        {"sitewide.duplicate_title", "sitewide.duplicate_description"}
        <= {issue.code for issue in page.issues}
        for page in checked
    )
    assert all(page.score == 90 for page in checked)


def test_comparison_and_csv_export() -> None:
    baseline_page = PageAudit(
        url="https://example.test/",
        final_url="https://example.test/",
        status_code=200,
        score=95,
        issues=[
            AuditIssue(
                code="old.issue",
                category="test",
                severity=Severity.WARNING,
                message="old",
            )
        ],
    )
    current_page = PageAudit(
        url="https://example.test/",
        final_url="https://example.test/",
        status_code=200,
        score=99,
        issues=[
            AuditIssue(
                code="new.issue",
                category="test",
                severity=Severity.INFO,
                message="new",
            )
        ],
    )
    baseline = report("before", 95, [baseline_page])
    current = report("after", 99, [current_page])

    comparison = compare_audits(baseline, current)
    insights = build_insights(current)
    rows = list(csv.DictReader(io.StringIO(audit_to_csv(current))))
    jsonl_rows = [json.loads(line) for line in audit_to_jsonl(current).splitlines()]

    assert comparison.score_change == 4
    assert comparison.new_issue_codes == ["new.issue"]
    assert comparison.resolved_issue_codes == ["old.issue"]
    assert insights.grade == "A"
    assert insights.total_issues == 1
    assert insights.top_issues[0].code == "new.issue"
    assert rows[0]["issue_codes"] == "new.issue"
    assert jsonl_rows[0]["audit_id"] == "after"
    assert jsonl_rows[0]["issues"][0]["code"] == "new.issue"


def test_sitewide_link_graph_and_sitemap_coverage() -> None:
    root = PageAudit(
        url="https://example.test/",
        final_url="https://example.test/",
        status_code=200,
        internal_link_targets=["https://example.test/missing"],
    )
    missing = PageAudit(
        url="https://example.test/missing",
        final_url="https://example.test/missing",
        status_code=404,
        crawl_depth=1,
    )
    sitemap_page = PageAudit(
        url="https://example.test/from-sitemap",
        final_url="https://example.test/from-sitemap",
        status_code=200,
        crawl_depth=1,
        discovered_from="sitemap",
    )

    checked = apply_sitewide_checks([root, missing, sitemap_page])
    coverage = build_sitemap_coverage(report("links", 80, checked))

    assert "link.broken_internal" in {issue.code for issue in checked[0].issues}
    assert checked[1].inbound_internal_links == 1
    assert "sitewide.orphan_page" in {issue.code for issue in checked[2].issues}
    assert coverage.sampled_urls == 1
    assert coverage.healthy_urls == 1
    assert coverage.orphaned_urls == 1


def test_audit_trend_preserves_report_order() -> None:
    earlier = report("earlier", 70, [])
    later = report("later", 90, [])

    trend = build_trend("https://example.test/", [earlier, later])

    assert [point.audit_id for point in trend.points] == ["earlier", "later"]
    assert [point.score for point in trend.points] == [70, 90]
