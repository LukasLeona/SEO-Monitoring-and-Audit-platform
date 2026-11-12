from fastapi.testclient import TestClient

from seo_monitor.api import create_app
from seo_monitor.config import Settings


def test_health_and_missing_audit(tmp_path) -> None:
    app = create_app(Settings(database_path=str(tmp_path / "api.db"), app_env="test"))

    with TestClient(app) as client:
        health = client.get("/health", headers={"X-Request-ID": "test-request"})
        ready = client.get("/health/ready")
        metrics = client.get("/api/v1/system/metrics")
        missing = client.get("/api/v1/audits/unknown")

    assert health.status_code == 200
    assert health.json() == {"status": "ok", "environment": "test"}
    assert health.headers["X-Request-ID"] == "test-request"
    assert "X-Process-Time-Ms" in health.headers
    assert ready.json() == {"status": "ready", "schema_version": 1}
    assert "seo_audits_total 0" in metrics.text
    assert missing.status_code == 404
