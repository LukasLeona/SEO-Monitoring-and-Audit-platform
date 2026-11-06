import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from seo_monitor.models import AuditJob, AuditJobStatus, AuditRequest
from seo_monitor.repository import AuditRepository
from seo_monitor.service import AuditService
from seo_monitor.webhook import WebhookDeliveryError, WebhookNotifier


class AuditJobService:
    def __init__(
        self,
        audit_service: AuditService,
        repository: AuditRepository,
        tasks: set[asyncio.Task[None]],
        notifier: WebhookNotifier | None = None,
    ) -> None:
        self.audit_service = audit_service
        self.repository = repository
        self.tasks = tasks
        self.notifier = notifier

    async def submit(self, request: AuditRequest) -> AuditJob:
        job = AuditJob(
            id=str(uuid4()),
            status=AuditJobStatus.QUEUED,
            request=request,
        )
        await self.repository.save_job(job)
        task = asyncio.create_task(self._run(job), name=f"audit-job-{job.id}")
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return job

    async def _run(self, job: AuditJob) -> None:
        running = job.model_copy(
            update={"status": AuditJobStatus.RUNNING, "updated_at": datetime.now(UTC)}
        )
        await self.repository.save_job(running)
        try:
            report = await self.audit_service.run(job.request)
        except Exception as exc:
            failed = running.model_copy(
                update={
                    "status": AuditJobStatus.FAILED,
                    "error": str(exc),
                    "updated_at": datetime.now(UTC),
                }
            )
            await self.repository.save_job(failed)
            return

        notification_error = None
        if self.notifier:
            try:
                await self.notifier.send(report)
            except WebhookDeliveryError as exc:
                notification_error = str(exc)

        completed = running.model_copy(
            update={
                "status": AuditJobStatus.COMPLETED,
                "audit_id": report.id,
                "notification_error": notification_error,
                "updated_at": datetime.now(UTC),
            }
        )
        await self.repository.save_job(completed)
