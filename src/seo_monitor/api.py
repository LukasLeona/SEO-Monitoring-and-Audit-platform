import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.responses import Response

from seo_monitor.api_security import configure_api_security
from seo_monitor.comparison import compare_audits
from seo_monitor.config import Settings, get_settings
from seo_monitor.exporter import audit_to_csv
from seo_monitor.gsc import GSCClient, GSCError
from seo_monitor.insights import build_insights
from seo_monitor.jobs import AuditJobService
from seo_monitor.models import (
    AuditComparison,
    AuditInsights,
    AuditJob,
    AuditJobStatus,
    AuditReport,
    AuditRequest,
    AuditSummary,
    GSCQuery,
    GSCResponse,
    Monitor,
    MonitorCreate,
)
from seo_monitor.monitoring import MonitoringService
from seo_monitor.observability import add_request_tracing, configure_logging
from seo_monitor.repository import AuditRepository
from seo_monitor.service import AuditService
from seo_monitor.webhook import WebhookNotifier


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    configure_logging(app_settings.log_level)
    repository = AuditRepository(app_settings.database_path)
    tasks: set[asyncio.Task[None]] = set()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        await repository.initialize()
        app.state.settings = app_settings
        app.state.repository = repository
        app.state.audit_service = AuditService(app_settings, repository)
        app.state.audit_job_service = AuditJobService(
            app.state.audit_service,
            repository,
            tasks,
            WebhookNotifier(app_settings),
        )
        app.state.monitoring_service = MonitoringService(
            app_settings,
            repository,
            app.state.audit_job_service,
        )
        scheduler = asyncio.create_task(
            app.state.monitoring_service.scheduler(),
            name="monitor-scheduler",
        )
        yield
        scheduler.cancel()
        await asyncio.gather(scheduler, return_exceptions=True)
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    app = FastAPI(
        title=app_settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
    )
    configure_api_security(app, app_settings)
    add_request_tracing(app)

    def audit_service(request: Request) -> AuditService:
        return request.app.state.audit_service

    def audit_repository(request: Request) -> AuditRepository:
        return request.app.state.repository

    def audit_job_service(request: Request) -> AuditJobService:
        return request.app.state.audit_job_service

    def monitoring_service(request: Request) -> MonitoringService:
        return request.app.state.monitoring_service

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "environment": app_settings.app_env}

    @app.post(
        "/api/v1/audits",
        response_model=AuditReport,
        status_code=status.HTTP_201_CREATED,
        tags=["audits"],
    )
    async def create_audit(
        payload: AuditRequest,
        service: AuditService = Depends(audit_service),
    ) -> AuditReport:
        return await service.run(payload)

    @app.post(
        "/api/v1/jobs",
        response_model=AuditJob,
        status_code=status.HTTP_202_ACCEPTED,
        tags=["jobs"],
    )
    async def create_audit_job(
        payload: AuditRequest,
        jobs: AuditJobService = Depends(audit_job_service),
    ) -> AuditJob:
        return await jobs.submit(payload)

    @app.get("/api/v1/jobs", response_model=list[AuditJob], tags=["jobs"])
    async def list_audit_jobs(
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
        job_status: AuditJobStatus | None = Query(default=None, alias="status"),
        repo: AuditRepository = Depends(audit_repository),
    ) -> list[AuditJob]:
        return await repo.list_jobs(limit, offset, job_status)

    @app.get("/api/v1/jobs/{job_id}", response_model=AuditJob, tags=["jobs"])
    async def get_audit_job(
        job_id: str,
        repo: AuditRepository = Depends(audit_repository),
    ) -> AuditJob:
        job = await repo.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Audit job not found")
        return job

    @app.post(
        "/api/v1/monitors",
        response_model=Monitor,
        status_code=status.HTTP_201_CREATED,
        tags=["monitors"],
    )
    async def create_monitor(
        payload: MonitorCreate,
        monitors: MonitoringService = Depends(monitoring_service),
    ) -> Monitor:
        return await monitors.create(payload)

    @app.get("/api/v1/monitors", response_model=list[Monitor], tags=["monitors"])
    async def list_monitors(
        repo: AuditRepository = Depends(audit_repository),
    ) -> list[Monitor]:
        return await repo.list_monitors()

    @app.patch(
        "/api/v1/monitors/{monitor_id}",
        response_model=Monitor,
        tags=["monitors"],
    )
    async def update_monitor(
        monitor_id: str,
        enabled: bool,
        monitors: MonitoringService = Depends(monitoring_service),
    ) -> Monitor:
        monitor = await monitors.set_enabled(monitor_id, enabled)
        if monitor is None:
            raise HTTPException(status_code=404, detail="Monitor not found")
        return monitor

    @app.get("/api/v1/audits", response_model=list[AuditSummary], tags=["audits"])
    async def list_audits(
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
        root_url: str | None = None,
        min_score: int | None = Query(default=None, ge=0, le=100),
        max_score: int | None = Query(default=None, ge=0, le=100),
        repo: AuditRepository = Depends(audit_repository),
    ) -> list[AuditSummary]:
        if min_score is not None and max_score is not None and min_score > max_score:
            raise HTTPException(
                status_code=422,
                detail="min_score must be less than or equal to max_score",
            )
        return await repo.list(
            limit,
            offset,
            root_url,
            min_score,
            max_score,
        )

    @app.get("/api/v1/audits/{audit_id}", response_model=AuditReport, tags=["audits"])
    async def get_audit(
        audit_id: str,
        repo: AuditRepository = Depends(audit_repository),
    ) -> AuditReport:
        report = await repo.get(audit_id)
        if report is None:
            raise HTTPException(status_code=404, detail="Audit not found")
        return report

    @app.get(
        "/api/v1/audits/{audit_id}/compare",
        response_model=AuditComparison,
        tags=["audits"],
    )
    async def compare_audit(
        audit_id: str,
        baseline_id: str | None = None,
        repo: AuditRepository = Depends(audit_repository),
    ) -> AuditComparison:
        current = await repo.get(audit_id)
        if current is None:
            raise HTTPException(status_code=404, detail="Audit not found")
        baseline = await repo.get(baseline_id) if baseline_id else await repo.previous(current)
        if baseline is None:
            raise HTTPException(status_code=404, detail="Baseline audit not found")
        return compare_audits(baseline, current)

    @app.get(
        "/api/v1/audits/{audit_id}/insights",
        response_model=AuditInsights,
        tags=["audits"],
    )
    async def audit_insights(
        audit_id: str,
        repo: AuditRepository = Depends(audit_repository),
    ) -> AuditInsights:
        report = await repo.get(audit_id)
        if report is None:
            raise HTTPException(status_code=404, detail="Audit not found")
        return build_insights(report)

    @app.get(
        "/api/v1/audits/{audit_id}/export.csv",
        response_class=Response,
        tags=["audits"],
    )
    async def export_audit(
        audit_id: str,
        repo: AuditRepository = Depends(audit_repository),
    ) -> Response:
        report = await repo.get(audit_id)
        if report is None:
            raise HTTPException(status_code=404, detail="Audit not found")
        return Response(
            content=audit_to_csv(report),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="seo-audit-{report.id}.csv"'},
        )

    @app.post("/api/v1/gsc/query", response_model=GSCResponse, tags=["search-console"])
    async def query_search_console(payload: GSCQuery) -> GSCResponse:
        try:
            return await GSCClient(app_settings).query(payload)
        except GSCError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    return app


app = create_app()
