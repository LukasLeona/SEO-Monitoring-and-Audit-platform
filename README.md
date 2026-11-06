# SEO Monitoring and Audit Platform

An API-first technical SEO crawler that audits on-page signals, stores audit
history, renders JavaScript when needed, and queries Google Search Console.

## Features

- FastAPI endpoints with generated OpenAPI documentation
- bounded same-origin crawling with redirect and response-size limits
- SSRF protection for private, loopback, link-local, and reserved addresses
- Beautiful Soup checks for metadata, headings, canonicals, indexability,
  image alt text, mobile/social tags, thin content, and JSON-LD
- robots.txt enforcement, crawl-delay support, and XML sitemap discovery
- sitewide duplicate title and description detection
- weighted page and site scores
- optional Playwright rendering for JavaScript-heavy sites
- Google Search Console Search Analytics queries
- SQLite audit history
- historical comparisons, background jobs, recurring monitors, and CSV exports
- JSON request logs with request IDs and processing-time headers
- optional API-key authentication, CORS allowlists, and hardened response headers
- actionable remediation guidance and prioritized audit insights
- signed completion webhooks for background and scheduled audits
- CLI, Docker image, tests, linting, and GitHub Actions

## Quick start

Install [uv](https://docs.astral.sh/uv/), then run:

```bash
uv sync --extra dev
uv run seo-monitor serve
```

Open <http://127.0.0.1:8000/docs> for the interactive API documentation.

Run a one-page audit:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/audits \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com","max_pages":10,"use_browser":false,"respect_robots":true,"use_sitemap":true}'
```

For longer audits, submit the same payload to `POST /api/v1/jobs` and poll
`GET /api/v1/jobs/{job_id}`. This keeps the HTTP request short while the crawl
runs in the background.

Create a daily monitor:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/monitors \
  -H "Content-Type: application/json" \
  -d '{"name":"Daily homepage audit","request":{"url":"https://example.com","max_pages":10},"interval_minutes":1440,"run_immediately":true}'
```

Compare an audit with the previous audit for the same root URL through
`GET /api/v1/audits/{audit_id}/compare`, or supply `baseline_id` explicitly.
Download page-level results from `GET /api/v1/audits/{audit_id}/export.csv`.
Use `GET /api/v1/audits/{audit_id}/insights` for the prioritized issue list,
affected URLs, audit grade, indexable-page count, and slowest pages.

For JavaScript-rendered audits, install Chromium once and set
`use_browser` to `true`:

```bash
uv run playwright install chromium
```

The CLI can run the same audit without starting a server:

```bash
uv run seo-monitor audit https://example.com --max-pages 5
```

## Google Search Console

Enable the Search Console API, grant the service account access to the Search
Console property, and set `SEO_GSC_CREDENTIALS_FILE` to the JSON credential
path. Application Default Credentials are used when that setting is absent.

```bash
curl -X POST http://127.0.0.1:8000/api/v1/gsc/query \
  -H "Content-Type: application/json" \
  -d '{"site_url":"https://example.com/","start_date":"2026-10-01","end_date":"2026-10-31","dimensions":["date"],"row_limit":1000}'
```

## Configuration

Copy `.env.example` to `.env`. Every setting uses the `SEO_` prefix.
Private hosts are blocked by default. Only enable `SEO_ALLOW_PRIVATE_HOSTS`
for trusted local development targets.

Transient 429 and 5xx responses are retried with bounded exponential backoff.
Every response includes `X-Request-ID` and `X-Process-Time-Ms`; logs use
newline-delimited JSON for straightforward ingestion.

Set `SEO_API_KEY` to require that value in the `X-API-Key` header for every
`/api/v1` route. The interactive OpenAPI UI automatically exposes the API-key
authorization control when protection is enabled. Configure
`SEO_CORS_ORIGINS` as a comma-separated allowlist when a browser dashboard
calls the API from another origin.

Set `SEO_WEBHOOK_URL` to receive `audit.completed` events from background and
scheduled audits. When `SEO_WEBHOOK_SECRET` is present, the raw JSON body is
signed with HMAC-SHA256 in the `X-SEO-Signature` header. Webhook destinations
pass the same public-address checks as crawl targets.

## Development

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

Audit reports are stored in `seo_monitor.db` by default. Credentials, local
databases, virtual environments, and environment files are ignored by Git.

See [Architecture](docs/architecture.md) for the component flow and operational
constraints, and [API guide](docs/api.md) for the main endpoint workflows.




