import argparse
import asyncio
import json
from pathlib import Path

import uvicorn

from seo_monitor.config import get_settings
from seo_monitor.exporter import audit_to_csv, audit_to_jsonl
from seo_monitor.models import AuditRequest
from seo_monitor.repository import AuditRepository
from seo_monitor.service import AuditService


async def _audit(args: argparse.Namespace) -> None:
    settings = get_settings()
    repository = AuditRepository(settings.database_path)
    await repository.initialize()
    report = await AuditService(settings, repository).run(
        AuditRequest(
            url=args.url,
            max_pages=args.max_pages,
            max_depth=args.max_depth,
            include_paths=args.include_path,
            exclude_paths=args.exclude_path,
            use_browser=args.browser,
            respect_robots=not args.ignore_robots,
            use_sitemap=not args.ignore_sitemap,
        )
    )
    print(report.model_dump_json(indent=2))


async def _history(limit: int) -> None:
    settings = get_settings()
    repository = AuditRepository(settings.database_path)
    await repository.initialize()
    summaries = await repository.list(limit=limit)
    print(
        json.dumps(
            [summary.model_dump(mode="json") for summary in summaries],
            indent=2,
        )
    )


async def _stats() -> None:
    settings = get_settings()
    repository = AuditRepository(settings.database_path)
    await repository.initialize()
    print((await repository.stats()).model_dump_json(indent=2))


def _write_export(path: str, content: str) -> Path:
    output_path = Path(path)
    output_path.write_text(content, encoding="utf-8", newline="")
    return output_path.resolve()


async def _export(args: argparse.Namespace) -> None:
    settings = get_settings()
    repository = AuditRepository(settings.database_path)
    await repository.initialize()
    report = await repository.get(args.audit_id)
    if report is None:
        raise SystemExit(f"Audit not found: {args.audit_id}")

    content = audit_to_csv(report) if args.format == "csv" else audit_to_jsonl(report)
    if args.output:
        print(await asyncio.to_thread(_write_export, args.output, content))
    else:
        print(content, end="")


def main() -> None:
    parser = argparse.ArgumentParser(description="SEO monitoring and audit platform")
    subcommands = parser.add_subparsers(dest="command", required=True)

    serve = subcommands.add_parser("serve", help="run the FastAPI server")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", default=8000, type=int)

    audit = subcommands.add_parser("audit", help="audit a website")
    audit.add_argument("url")
    audit.add_argument("--max-pages", default=1, type=int)
    audit.add_argument("--max-depth", default=5, type=int)
    audit.add_argument("--include-path", action="append", default=[])
    audit.add_argument("--exclude-path", action="append", default=[])
    audit.add_argument("--browser", action="store_true")
    audit.add_argument("--ignore-robots", action="store_true")
    audit.add_argument("--ignore-sitemap", action="store_true")

    history = subcommands.add_parser("history", help="list recent audit reports")
    history.add_argument("--limit", default=20, type=int)

    subcommands.add_parser("stats", help="show stored audit and monitor counts")

    export = subcommands.add_parser("export", help="export a stored audit report")
    export.add_argument("audit_id")
    export.add_argument("--format", choices=("csv", "jsonl"), default="jsonl")
    export.add_argument("--output", help="write the export to this file")

    args = parser.parse_args()
    if args.command == "serve":
        uvicorn.run("seo_monitor.api:app", host=args.host, port=args.port)
    elif args.command == "audit":
        asyncio.run(_audit(args))
    elif args.command == "history":
        asyncio.run(_history(args.limit))
    elif args.command == "stats":
        asyncio.run(_stats())
    else:
        asyncio.run(_export(args))


if __name__ == "__main__":
    main()
