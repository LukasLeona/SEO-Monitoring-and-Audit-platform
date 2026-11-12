from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path

from seo_monitor.models import AuditJob, AuditReport, AuditSummary, Monitor

SCHEMA_VERSION = 1


class AuditRepository:
    def __init__(self, database_path: str) -> None:
        self.database_path = database_path

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=5000")
        return connection

    def _initialize_sync(self) -> None:
        path = Path(self.database_path)
        if path.parent != Path("."):
            path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=NORMAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
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
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_jobs (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    job_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS monitors (
                    id TEXT PRIMARY KEY,
                    enabled INTEGER NOT NULL,
                    next_run_at TEXT NOT NULL,
                    monitor_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_audits_root_started "
                "ON audits(root_url, started_at DESC)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_jobs_status_created "
                "ON audit_jobs(status, created_at DESC)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_monitors_due ON monitors(enabled, next_run_at)"
            )
            connection.execute(
                "INSERT OR IGNORE INTO schema_migrations(version) VALUES (?)",
                (SCHEMA_VERSION,),
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

    def _save_job_sync(self, job: AuditJob) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO audit_jobs
                    (id, status, created_at, updated_at, job_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    job.id,
                    job.status,
                    job.created_at.isoformat(),
                    job.updated_at.isoformat(),
                    job.model_dump_json(),
                ),
            )

    async def save_job(self, job: AuditJob) -> None:
        await asyncio.to_thread(self._save_job_sync, job)

    def _get_job_sync(self, job_id: str) -> AuditJob | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT job_json FROM audit_jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
        return AuditJob.model_validate_json(row["job_json"]) if row else None

    async def get_job(self, job_id: str) -> AuditJob | None:
        return await asyncio.to_thread(self._get_job_sync, job_id)

    def _list_jobs_sync(self, limit: int) -> list[AuditJob]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT job_json
                FROM audit_jobs
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [AuditJob.model_validate_json(row["job_json"]) for row in rows]

    async def list_jobs(self, limit: int = 20) -> list[AuditJob]:
        return await asyncio.to_thread(self._list_jobs_sync, limit)

    def _save_monitor_sync(self, monitor: Monitor) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO monitors
                    (id, enabled, next_run_at, monitor_json)
                VALUES (?, ?, ?, ?)
                """,
                (
                    monitor.id,
                    int(monitor.enabled),
                    monitor.next_run_at.isoformat(),
                    monitor.model_dump_json(),
                ),
            )

    async def save_monitor(self, monitor: Monitor) -> None:
        await asyncio.to_thread(self._save_monitor_sync, monitor)

    def _get_monitor_sync(self, monitor_id: str) -> Monitor | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT monitor_json FROM monitors WHERE id = ?",
                (monitor_id,),
            ).fetchone()
        return Monitor.model_validate_json(row["monitor_json"]) if row else None

    async def get_monitor(self, monitor_id: str) -> Monitor | None:
        return await asyncio.to_thread(self._get_monitor_sync, monitor_id)

    def _list_monitors_sync(self) -> list[Monitor]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT monitor_json FROM monitors ORDER BY next_run_at"
            ).fetchall()
        return [Monitor.model_validate_json(row["monitor_json"]) for row in rows]

    async def list_monitors(self) -> list[Monitor]:
        return await asyncio.to_thread(self._list_monitors_sync)

    def _due_monitors_sync(self, now: str) -> list[Monitor]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT monitor_json
                FROM monitors
                WHERE enabled = 1 AND next_run_at <= ?
                ORDER BY next_run_at
                """,
                (now,),
            ).fetchall()
        return [Monitor.model_validate_json(row["monitor_json"]) for row in rows]

    async def due_monitors(self, now: str) -> list[Monitor]:
        return await asyncio.to_thread(self._due_monitors_sync, now)
