import argparse
import asyncio

import uvicorn

from seo_monitor.config import get_settings
from seo_monitor.models import AuditRequest
from seo_monitor.repository import AuditRepository
from seo_monitor.service import AuditService


async def _audit(url: str, max_pages: int, use_browser: bool) -> None:
    settings = get_settings()
    repository = AuditRepository(settings.database_path)
    await repository.initialize()
    report = await AuditService(settings, repository).run(
        AuditRequest(url=url, max_pages=max_pages, use_browser=use_browser)
    )
    print(report.model_dump_json(indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="SEO monitoring and audit platform")
    subcommands = parser.add_subparsers(dest="command", required=True)

    serve = subcommands.add_parser("serve", help="run the FastAPI server")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", default=8000, type=int)

    audit = subcommands.add_parser("audit", help="audit a website")
    audit.add_argument("url")
    audit.add_argument("--max-pages", default=1, type=int)
    audit.add_argument("--browser", action="store_true")

    args = parser.parse_args()
    if args.command == "serve":
        uvicorn.run("seo_monitor.api:app", host=args.host, port=args.port)
    else:
        asyncio.run(_audit(args.url, args.max_pages, args.browser))


if __name__ == "__main__":
    main()

