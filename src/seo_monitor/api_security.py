import secrets

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from starlette.middleware.cors import CORSMiddleware

from seo_monitor.config import Settings


def configure_api_security(app: FastAPI, settings: Settings) -> None:
    origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=False,
            allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
            allow_headers=["Content-Type", "X-API-Key", "X-Request-ID"],
        )

    @app.middleware("http")
    async def security_headers_and_auth(request: Request, call_next):
        configured_key = settings.api_key.get_secret_value() if settings.api_key else None
        if configured_key and request.url.path.startswith("/api/v1"):
            provided_key = request.headers.get("x-api-key", "")
            if not secrets.compare_digest(provided_key, configured_key):
                response = JSONResponse(
                    status_code=401,
                    content={"detail": "A valid X-API-Key header is required"},
                    headers={"WWW-Authenticate": "ApiKey"},
                )
                _add_security_headers(response)
                return response

        response = await call_next(request)
        _add_security_headers(response)
        return response


def _add_security_headers(response: Response) -> None:
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
