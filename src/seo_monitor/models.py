from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, HttpUrl, model_validator


class Severity(StrEnum):
    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class AuditIssue(BaseModel):
    code: str
    category: str
    severity: Severity
    message: str
    evidence: dict[str, Any] = Field(default_factory=dict)


class PageAudit(BaseModel):
    url: str
    final_url: str
    status_code: int
    content_type: str | None = None
    title: str | None = None
    meta_description: str | None = None
    h1: list[str] = Field(default_factory=list)
    headings: list[str] = Field(default_factory=list)
    canonical: str | None = None
    meta_robots: str | None = None
    has_viewport: bool = False
    has_open_graph: bool = False
    has_twitter_card: bool = False
    hreflang_count: int = 0
    structured_data_types: list[str] = Field(default_factory=list)
    word_count: int = 0
    internal_links: int = 0
    external_links: int = 0
    images: int = 0
    images_without_alt: int = 0
    score: int = Field(default=100, ge=0, le=100)
    duration_ms: int = 0
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    issues: list[AuditIssue] = Field(default_factory=list)


class AuditRequest(BaseModel):
    url: HttpUrl
    max_pages: int = Field(default=1, ge=1, le=250)
    use_browser: bool = False
    respect_robots: bool = True
    use_sitemap: bool = True


class AuditJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AuditJob(BaseModel):
    id: str
    status: AuditJobStatus
    request: AuditRequest
    audit_id: str | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class MonitorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    request: AuditRequest
    interval_minutes: int = Field(default=1440, ge=15, le=43_200)
    run_immediately: bool = True


class Monitor(BaseModel):
    id: str
    name: str
    request: AuditRequest
    interval_minutes: int
    enabled: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    next_run_at: datetime
    last_job_id: str | None = None


class AuditReport(BaseModel):
    id: str
    root_url: str
    started_at: datetime
    completed_at: datetime
    score: int = Field(ge=0, le=100)
    pages_scanned: int
    issue_summary: dict[Severity, int]
    pages: list[PageAudit]


class AuditSummary(BaseModel):
    id: str
    root_url: str
    score: int
    pages_scanned: int
    started_at: datetime
    completed_at: datetime


class AuditComparison(BaseModel):
    baseline_id: str
    current_id: str
    score_change: int
    pages_change: int
    issue_changes: dict[Severity, int]
    new_issue_codes: list[str]
    resolved_issue_codes: list[str]


class GSCQuery(BaseModel):
    site_url: str = Field(min_length=1)
    start_date: date
    end_date: date
    dimensions: list[str] = Field(default_factory=lambda: ["date"])
    row_limit: int = Field(default=1000, ge=1, le=25_000)

    @model_validator(mode="after")
    def validate_date_range(self) -> "GSCQuery":
        if self.start_date > self.end_date:
            raise ValueError("start_date must be on or before end_date")
        return self


class GSCRow(BaseModel):
    keys: list[str] = Field(default_factory=list)
    clicks: float = 0
    impressions: float = 0
    ctr: float = 0
    position: float = 0


class GSCResponse(BaseModel):
    site_url: str
    rows: list[GSCRow]
