from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl, model_validator

ISSUE_REMEDIATIONS: dict[str, str] = {
    "http.server_error": (
        "Inspect application and upstream logs, then restore a stable 2xx response."
    ),
    "http.client_error": (
        "Fix the URL, redirect it to a relevant page, or restore the missing resource."
    ),
    "content.non_html": "Serve indexable pages with an HTML content type.",
    "title.missing": "Add a unique, descriptive title element to the page head.",
    "title.short": "Expand the title with specific topic or intent terms without adding filler.",
    "title.long": "Shorten the title so its most useful terms are likely to remain visible.",
    "description.missing": "Add a unique meta description that summarizes the page benefit.",
    "description.length": (
        "Rewrite the meta description to communicate the page clearly and concisely."
    ),
    "h1.missing": "Add one clear H1 that describes the primary page topic.",
    "h1.multiple": "Keep one primary H1 and move subsections to lower heading levels.",
    "heading.skipped_level": "Use sequential heading levels so the document outline is clear.",
    "canonical.missing": "Add a self-referencing or intentionally selected canonical URL.",
    "canonical.multiple": "Keep exactly one canonical link in the document head.",
    "canonical.insecure": "Point HTTPS pages to an HTTPS canonical URL.",
    "hreflang.invalid": "Give every hreflang entry a valid language code and absolute target.",
    "hreflang.duplicate": "Keep only one alternate URL for each hreflang value.",
    "hreflang.x_default_missing": "Add an x-default alternate for unmatched languages.",
    "html.lang_missing": "Set the html lang attribute to the page's primary language.",
    "robots.noindex": "Remove noindex when the page should be eligible for search results.",
    "mobile.viewport_missing": "Add a responsive viewport meta tag for mobile rendering.",
    "social.open_graph_missing": "Add Open Graph title, description, image, and URL metadata.",
    "social.twitter_card_missing": "Add a Twitter card type and supporting social metadata.",
    "image.alt_missing": "Add meaningful alt text, or an empty alt value for decorative images.",
    "link.empty_text": "Give links descriptive visible text or an accessible label.",
    "content.thin": "Add original, useful content that fully answers the page's search intent.",
    "structured_data.invalid_json": "Validate and correct the JSON-LD syntax before deployment.",
    "robots.disallowed": "Review the robots.txt rule if this page should be crawlable.",
    "fetch.failed": "Check DNS, TLS, timeouts, and server availability for the failed URL.",
    "sitewide.duplicate_title": "Give every indexable page a distinct, intent-specific title.",
    "sitewide.duplicate_description": "Write a distinct description for each indexable page.",
    "sitewide.duplicate_content": (
        "Consolidate substantially identical pages or make each page uniquely useful."
    ),
}


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
    remediation: str | None = None

    @model_validator(mode="after")
    def add_default_remediation(self) -> "AuditIssue":
        if self.remediation is None:
            self.remediation = ISSUE_REMEDIATIONS.get(self.code)
        return self


class PageAudit(BaseModel):
    url: str
    final_url: str
    status_code: int
    crawl_depth: int = 0
    discovered_from: str | None = None
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
    hreflang_values: list[str] = Field(default_factory=list)
    structured_data_types: list[str] = Field(default_factory=list)
    word_count: int = 0
    content_hash: str | None = None
    internal_links: int = 0
    external_links: int = 0
    empty_links: int = 0
    images: int = 0
    images_without_alt: int = 0
    score: int = Field(default=100, ge=0, le=100)
    duration_ms: int = 0
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    issues: list[AuditIssue] = Field(default_factory=list)


class AuditRequest(BaseModel):
    url: HttpUrl
    max_pages: int = Field(default=1, ge=1, le=250)
    max_depth: int = Field(default=5, ge=0, le=20)
    include_paths: list[str] = Field(default_factory=list, max_length=20)
    exclude_paths: list[str] = Field(default_factory=list, max_length=20)
    use_browser: bool = False
    respect_robots: bool = True
    use_sitemap: bool = True


class AuditJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AuditJob(BaseModel):
    id: str
    status: AuditJobStatus
    request: AuditRequest
    audit_id: str | None = None
    error: str | None = None
    notification_error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class MonitorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    request: AuditRequest
    interval_minutes: int = Field(default=1440, ge=15, le=43_200)
    run_immediately: bool = True


class MonitorUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    request: AuditRequest | None = None
    interval_minutes: int | None = Field(default=None, ge=15, le=43_200)
    enabled: bool | None = None

    @model_validator(mode="after")
    def require_change(self) -> "MonitorUpdate":
        if not self.model_fields_set:
            raise ValueError("at least one monitor field must be provided")
        return self


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


class InsightIssue(BaseModel):
    code: str
    category: str
    severity: Severity
    occurrences: int
    affected_pages: list[str]
    remediation: str | None = None


class SlowPage(BaseModel):
    url: str
    duration_ms: int
    status_code: int


class AuditInsights(BaseModel):
    audit_id: str
    score: int
    grade: str
    total_issues: int
    indexable_pages: int
    category_totals: dict[str, int]
    top_issues: list[InsightIssue]
    slowest_pages: list[SlowPage]


class GSCFilter(BaseModel):
    dimension: Literal["query", "page", "country", "device", "searchAppearance"]
    operator: Literal[
        "contains",
        "equals",
        "notContains",
        "notEquals",
        "includingRegex",
        "excludingRegex",
    ] = "equals"
    expression: str = Field(min_length=1, max_length=4096)


class GSCQuery(BaseModel):
    site_url: str = Field(min_length=1)
    start_date: date
    end_date: date
    dimensions: list[str] = Field(default_factory=lambda: ["date"])
    filters: list[GSCFilter] = Field(default_factory=list, max_length=20)
    search_type: Literal["web", "image", "video", "news", "discover", "googleNews"] = "web"
    aggregation_type: Literal["auto", "byPage", "byProperty"] = "auto"
    data_state: Literal["final", "all", "hourly_all"] = "final"
    row_limit: int = Field(default=1000, ge=1, le=25_000)
    start_row: int = Field(default=0, ge=0)

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
    response_aggregation_type: str | None = None
