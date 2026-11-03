# SEO Monitoring and Audit Platform

An API-first technical SEO crawler that audits on-page signals, stores audit
history, renders JavaScript when needed, and queries Google Search Console.

## Features

- FastAPI endpoints with generated OpenAPI documentation
- bounded same-origin crawling with redirect and response-size limits
- SSRF protection for private, loopback, link-local, and reserved addresses
- Beautiful Soup checks for metadata, headings, canonicals, indexability,
  image alt text, thin content, and JSON-LD
- weighted page and site scores
- optional Playwright rendering for JavaScript-heavy sites
- Google Search Console Search Analytics queries
- SQLite audit history
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
  -d '{"url":"https://example.com","max_pages":1,"use_browser":false}'
```

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

## Development

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

Audit reports are stored in `seo_monitor.db` by default. Credentials, local
databases, virtual environments, and environment files are ignored by Git.


