# API guide

The generated OpenAPI schema is available at `/openapi.json`, Swagger UI at
`/docs`, and ReDoc at `/redoc`. Health checks remain public at `/health`.
When `SEO_API_KEY` is configured, every `/api/v1` request must include
`X-API-Key`.

## Audit workflows

- `POST /api/v1/audits` runs a short audit synchronously.
- `POST /api/v1/jobs` queues a durable background audit.
- `GET /api/v1/jobs/{job_id}` returns queue state and the resulting audit ID.
- `POST /api/v1/jobs/{job_id}/cancel` cancels queued or in-process work.
- `GET /api/v1/audits/{audit_id}` returns the complete page-level report.
- `GET /api/v1/audits/{audit_id}/insights` returns prioritized actions.
- `GET /api/v1/audits/{audit_id}/compare` compares with the prior matching audit.
- `GET /api/v1/audits/{audit_id}/export.csv` downloads spreadsheet-ready rows.

Issue objects include a stable code, severity, category, evidence, and a
`remediation` field suitable for task creation.

Audit and job list endpoints accept `limit` and `offset`. Audit history can
filter by `root_url`, `min_score`, and `max_score`; jobs can filter by
`status`. Audit requests accept `max_depth`, `include_paths`, and
`exclude_paths` glob patterns. Each page result records `crawl_depth` and
`discovered_from`.

## Monitoring

`POST /api/v1/monitors` creates an interval-based audit definition. A monitor
can run immediately and then at intervals from 15 minutes to 30 days.
`PATCH /api/v1/monitors/{monitor_id}` accepts a JSON body with any of `name`,
`request`, `interval_minutes`, or `enabled`.
`POST /api/v1/monitors/{monitor_id}/run` starts an immediate manual run.

Completed jobs attempt webhook delivery when configured. A webhook failure is
recorded in the job's `notification_error` field and does not discard the
successful audit.

## Operations

- `GET /health` is a process liveness check.
- `GET /health/ready` confirms SQLite access and reports the schema version.
- `GET /api/v1/system/stats` returns structured storage counts.
- `GET /api/v1/system/metrics` returns Prometheus text exposition.

Search Console requests support `filters`, `search_type`, `aggregation_type`,
`data_state`, `start_row`, and `row_limit`.

