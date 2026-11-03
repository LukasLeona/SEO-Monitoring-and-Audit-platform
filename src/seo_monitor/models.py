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
    canonical: str | None = None
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

