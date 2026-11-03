from datetime import UTC, datetime

from seo_monitor.models import AuditReport, Severity
from seo_monitor.repository import AuditRepository


async def test_repository_round_trip(tmp_path) -> None:
    repository = AuditRepository(str(tmp_path / "audits.db"))
    await repository.initialize()
    now = datetime.now(UTC)
    report = AuditReport(
        id="audit-1",
        root_url="https://example.com/",
        started_at=now,
        completed_at=now,
        score=100,
        pages_scanned=0,
        issue_summary={severity: 0 for severity in Severity},
        pages=[],
    )

    await repository.save(report)

    assert await repository.get("audit-1") == report
    assert (await repository.list())[0].id == "audit-1"
