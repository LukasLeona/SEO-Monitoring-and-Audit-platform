import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from seo_monitor.config import Settings
from seo_monitor.jobs import AuditJobService
from seo_monitor.models import AuditJob, Monitor, MonitorCreate, MonitorUpdate
from seo_monitor.repository import AuditRepository


class MonitoringService:
    def __init__(
        self,
        settings: Settings,
        repository: AuditRepository,
        jobs: AuditJobService,
    ) -> None:
        self.settings = settings
        self.repository = repository
        self.jobs = jobs

    async def create(self, payload: MonitorCreate) -> Monitor:
        now = datetime.now(UTC)
        next_run = (
            now if payload.run_immediately else now + timedelta(minutes=payload.interval_minutes)
        )
        monitor = Monitor(
            id=str(uuid4()),
            name=payload.name,
            request=payload.request,
            interval_minutes=payload.interval_minutes,
            next_run_at=next_run,
        )
        await self.repository.save_monitor(monitor)
        return monitor

    async def update(
        self,
        monitor_id: str,
        payload: MonitorUpdate,
    ) -> Monitor | None:
        monitor = await self.repository.get_monitor(monitor_id)
        if monitor is None:
            return None
        changes = payload.model_dump(exclude_none=True)
        if "interval_minutes" in changes:
            changes["next_run_at"] = datetime.now(UTC) + timedelta(
                minutes=changes["interval_minutes"]
            )
        updated = monitor.model_copy(update=changes)
        await self.repository.save_monitor(updated)
        return updated

    async def run_now(self, monitor_id: str) -> tuple[Monitor, AuditJob] | None:
        monitor = await self.repository.get_monitor(monitor_id)
        if monitor is None:
            return None
        job = await self.jobs.submit(monitor.request)
        updated = monitor.model_copy(update={"last_job_id": job.id})
        await self.repository.save_monitor(updated)
        return updated, job

    async def run_due(self) -> int:
        now = datetime.now(UTC)
        due = await self.repository.due_monitors(now.isoformat())
        for monitor in due:
            job = await self.jobs.submit(monitor.request)
            updated = monitor.model_copy(
                update={
                    "last_job_id": job.id,
                    "next_run_at": now + timedelta(minutes=monitor.interval_minutes),
                }
            )
            await self.repository.save_monitor(updated)
        return len(due)

    async def scheduler(self) -> None:
        while True:
            await self.run_due()
            await asyncio.sleep(self.settings.monitor_poll_seconds)
