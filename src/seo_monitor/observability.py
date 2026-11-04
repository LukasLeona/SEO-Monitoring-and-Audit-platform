import json
import logging
import re
from contextvars import ContextVar
from datetime import UTC, datetime
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request

request_id_context: ContextVar[str] = ContextVar("request_id", default="-")
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", request_id_context.get()),
        }
        for key in ("method", "path", "status_code", "duration_ms"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, separators=(",", ":"))


def configure_logging(level: str) -> None:
    root = logging.getLogger()
    root.setLevel(level.upper())
    if not any(isinstance(handler.formatter, JsonFormatter) for handler in root.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        root.handlers.clear()
        root.addHandler(handler)


def add_request_tracing(app: FastAPI) -> None:
    logger = logging.getLogger("seo_monitor.http")

    @app.middleware("http")
    async def request_tracing(request: Request, call_next):
        supplied_id = request.headers.get("x-request-id", "")
        request_id = supplied_id if REQUEST_ID_PATTERN.fullmatch(supplied_id) else str(uuid4())
        token = request_id_context.set(request_id)
        started = perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "request failed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": round((perf_counter() - started) * 1000),
                },
            )
            raise
        else:
            duration_ms = round((perf_counter() - started) * 1000)
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time-Ms"] = str(duration_ms)
            logger.info(
                "request completed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                },
            )
            return response
        finally:
            request_id_context.reset(token)
