# Architecture

The platform has four execution paths:

1. A synchronous audit accepts an `AuditRequest`, chooses the HTTP or
   Playwright fetcher, crawls the site, applies page and sitewide checks, and
   saves one immutable report.
2. A background job persists its state before launching the same audit service.
   Job state survives process restarts, although an interrupted running job
   must be resubmitted.
3. A recurring monitor stores its next run time. The scheduler claims due
   monitors by advancing their next run before the crawl begins, preventing
   repeat submissions during normal operation.
4. Search Console queries run in a worker thread around Google's synchronous
   client and never block the event loop.

## Crawl safety

Targets and redirects are limited to HTTP(S). DNS results that are private,
loopback, link-local, or reserved are rejected. Playwright also checks each
resource request. Response sizes, redirects, retries, page counts, concurrency,
sitemap documents, and sitemap URLs are bounded.

Robots rules are loaded with the configured crawler user-agent. Disallowed URLs
are recorded as informational page results instead of fetched. Declared
sitemaps must remain on the root origin. Crawl delays force single-page batches.

## Storage

SQLite uses one connection per operation and WAL mode. Reports, jobs, and
monitors are stored as version-tolerant JSON alongside indexed fields used for
sorting and due-work queries. This keeps the first deployment simple; a
distributed deployment should replace SQLite and the in-process scheduler with
a shared database and worker queue.

