import asyncio
from datetime import UTC, datetime

from seo_monitor.config import Settings
from seo_monitor.jobs import AuditJobService
from seo_monitor.models import (
    AuditJob,
    AuditJobStatus,
    AuditReport,
    AuditRequest,
    MonitorCreate,
    Severity,
)
from seo_monitor.monitoring import MonitoringService
from seo_monitor.repository import AuditRepository


class StubAuditService:
    async def run(self, request: AuditRequest) -> AuditReport:
        now = datetime.now(UTC)
        return AuditReport(
            id="result-1",
            root_url=str(request.url),
            started_at=now,
            completed_at=now,
            score=100,
            pages_scanned=0,
            issue_summary={severity: 0 for severity in Severity},
            pages=[],
        )


async def test_background_job_reaches_completed_state(tmp_path) -> None:
    repository = AuditRepository(str(tmp_path / "jobs.db"))
    await repository.initialize()
    tasks: set[asyncio.Task[None]] = set()
    jobs = AuditJobService(StubAuditService(), repository, tasks)

    job = await jobs.submit(AuditRequest(url="https://example.test"))
    await asyncio.gather(*tasks)
    saved = await repository.get_job(job.id)

    assert saved is not None
    assert saved.status == AuditJobStatus.COMPLETED
    assert saved.audit_id == "result-1"


async def test_due_monitor_submits_job_and_advances_schedule(tmp_path) -> None:
    class StubJobs:
        async def submit(self, request: AuditRequest) -> AuditJob:
            return AuditJob(id="job-1", status=AuditJobStatus.QUEUED, request=request)

    repository = AuditRepository(str(tmp_path / "monitors.db"))
    await repository.initialize()
    service = MonitoringService(Settings(), repository, StubJobs())
    monitor = await service.create(
        MonitorCreate(
            name="Daily",
            request=AuditRequest(url="https://example.test"),
            run_immediately=True,
        )
    )

    assert await service.run_due() == 1
    saved = await repository.get_monitor(monitor.id)
    assert saved is not None
    assert saved.last_job_id == "job-1"
    assert saved.next_run_at > monitor.next_run_at
