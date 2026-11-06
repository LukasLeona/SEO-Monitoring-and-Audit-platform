# API guide

The generated OpenAPI schema is available at `/openapi.json`, Swagger UI at
`/docs`, and ReDoc at `/redoc`. Health checks remain public at `/health`.
When `SEO_API_KEY` is configured, every `/api/v1` request must include
`X-API-Key`.

## Audit workflows

- `POST /api/v1/audits` runs a short audit synchronously.
- `POST /api/v1/jobs` queues a durable background audit.
- `GET /api/v1/jobs/{job_id}` returns queue state and the resulting audit ID.
- `GET /api/v1/audits/{audit_id}` returns the complete page-level report.
- `GET /api/v1/audits/{audit_id}/insights` returns prioritized actions.
- `GET /api/v1/audits/{audit_id}/compare` compares with the prior matching audit.
- `GET /api/v1/audits/{audit_id}/export.csv` downloads spreadsheet-ready rows.

Issue objects include a stable code, severity, category, evidence, and a
`remediation` field suitable for task creation.

## Monitoring

`POST /api/v1/monitors` creates an interval-based audit definition. A monitor
can run immediately and then at intervals from 15 minutes to 30 days.
`PATCH /api/v1/monitors/{monitor_id}?enabled=false` pauses future runs.

Completed jobs attempt webhook delivery when configured. A webhook failure is
recorded in the job's `notification_error` field and does not discard the
successful audit.

