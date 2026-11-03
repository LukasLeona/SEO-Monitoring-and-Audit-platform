from fastapi.testclient import TestClient

from seo_monitor.api import create_app
from seo_monitor.config import Settings


def test_health_and_missing_audit(tmp_path) -> None:
    app = create_app(Settings(database_path=str(tmp_path / "api.db"), app_env="test"))

    with TestClient(app) as client:
        health = client.get("/health")
        missing = client.get("/api/v1/audits/unknown")

    assert health.status_code == 200
    assert health.json() == {"status": "ok", "environment": "test"}
    assert missing.status_code == 404
