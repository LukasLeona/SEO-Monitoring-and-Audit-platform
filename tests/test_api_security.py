from fastapi.testclient import TestClient

from seo_monitor.api import create_app
from seo_monitor.config import Settings


def test_api_key_protects_api_and_is_described_in_openapi(tmp_path) -> None:
    app = create_app(
        Settings(
            database_path=str(tmp_path / "secured.db"),
            api_key="test-secret",
            app_env="test",
        )
    )

    with TestClient(app) as client:
        unauthorized = client.get("/api/v1/audits")
        authorized = client.get(
            "/api/v1/audits",
            headers={"X-API-Key": "test-secret"},
        )
        health = client.get("/health")
        schema = client.get("/openapi.json").json()

    assert unauthorized.status_code == 401
    assert unauthorized.headers["X-Content-Type-Options"] == "nosniff"
    assert authorized.status_code == 200
    assert health.status_code == 200
    assert schema["components"]["securitySchemes"]["ApiKeyAuth"]["name"] == "X-API-Key"
    assert schema["paths"]["/api/v1/audits"]["get"]["security"] == [{"ApiKeyAuth": []}]


def test_configured_cors_origin_is_allowed(tmp_path) -> None:
    app = create_app(
        Settings(
            database_path=str(tmp_path / "cors.db"),
            cors_origins="https://dashboard.example.test",
            app_env="test",
        )
    )

    with TestClient(app) as client:
        response = client.options(
            "/api/v1/audits",
            headers={
                "Origin": "https://dashboard.example.test",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == 200
    assert response.headers["Access-Control-Allow-Origin"] == ("https://dashboard.example.test")
