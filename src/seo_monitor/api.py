from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status

from seo_monitor.config import Settings, get_settings
from seo_monitor.gsc import GSCClient, GSCError
from seo_monitor.models import (
    AuditReport,
    AuditRequest,
    AuditSummary,
    GSCQuery,
    GSCResponse,
)
from seo_monitor.repository import AuditRepository
from seo_monitor.service import AuditService


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    repository = AuditRepository(app_settings.database_path)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        await repository.initialize()
        app.state.settings = app_settings
        app.state.repository = repository
        app.state.audit_service = AuditService(app_settings, repository)
        yield

    app = FastAPI(
        title=app_settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
    )

    def audit_service(request: Request) -> AuditService:
        return request.app.state.audit_service

    def audit_repository(request: Request) -> AuditRepository:
        return request.app.state.repository

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

    @app.get("/api/v1/audits", response_model=list[AuditSummary], tags=["audits"])
    async def list_audits(
        limit: int = Query(default=20, ge=1, le=100),
        repo: AuditRepository = Depends(audit_repository),
    ) -> list[AuditSummary]:
        return await repo.list(limit)

    @app.get("/api/v1/audits/{audit_id}", response_model=AuditReport, tags=["audits"])
    async def get_audit(
        audit_id: str,
        repo: AuditRepository = Depends(audit_repository),
    ) -> AuditReport:
        report = await repo.get(audit_id)
        if report is None:
            raise HTTPException(status_code=404, detail="Audit not found")
        return report

    @app.post("/api/v1/gsc/query", response_model=GSCResponse, tags=["search-console"])
    async def query_search_console(payload: GSCQuery) -> GSCResponse:
        try:
            return await GSCClient(app_settings).query(payload)
        except GSCError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    return app


app = create_app()

