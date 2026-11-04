import asyncio
import sqlite3
from pathlib import Path

from seo_monitor.models import AuditReport, AuditSummary


class AuditRepository:
    def __init__(self, database_path: str) -> None:
        self.database_path = database_path

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize_sync(self) -> None:
        path = Path(self.database_path)
        if path.parent != Path("."):
            path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS audits (
                    id TEXT PRIMARY KEY,
                    root_url TEXT NOT NULL,
                    score INTEGER NOT NULL,
                    pages_scanned INTEGER NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT NOT NULL,
                    report_json TEXT NOT NULL
                )
                """
            )

    async def initialize(self) -> None:
        await asyncio.to_thread(self._initialize_sync)

    def _save_sync(self, report: AuditReport) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO audits
                    (id, root_url, score, pages_scanned, started_at, completed_at, report_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report.id,
                    report.root_url,
                    report.score,
                    report.pages_scanned,
                    report.started_at.isoformat(),
                    report.completed_at.isoformat(),
                    report.model_dump_json(),
                ),
            )

    async def save(self, report: AuditReport) -> None:
        await asyncio.to_thread(self._save_sync, report)

    def _get_sync(self, audit_id: str) -> AuditReport | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT report_json FROM audits WHERE id = ?",
                (audit_id,),
            ).fetchone()
        return AuditReport.model_validate_json(row["report_json"]) if row else None

    async def get(self, audit_id: str) -> AuditReport | None:
        return await asyncio.to_thread(self._get_sync, audit_id)

    def _list_sync(self, limit: int) -> list[AuditSummary]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, root_url, score, pages_scanned, started_at, completed_at
                FROM audits
                ORDER BY started_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [AuditSummary.model_validate(dict(row)) for row in rows]

    async def list(self, limit: int = 20) -> list[AuditSummary]:
        return await asyncio.to_thread(self._list_sync, limit)

    def _previous_sync(
        self,
        root_url: str,
        before_started_at: str,
        exclude_id: str,
    ) -> AuditReport | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT report_json
                FROM audits
                WHERE root_url = ? AND started_at < ? AND id != ?
                ORDER BY started_at DESC
                LIMIT 1
                """,
                (root_url, before_started_at, exclude_id),
            ).fetchone()
        return AuditReport.model_validate_json(row["report_json"]) if row else None

    async def previous(self, report: AuditReport) -> AuditReport | None:
        return await asyncio.to_thread(
            self._previous_sync,
            report.root_url,
            report.started_at.isoformat(),
            report.id,
        )
