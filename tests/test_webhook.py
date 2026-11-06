import hashlib
import hmac
from datetime import UTC, datetime

import respx
from httpx import Response

from seo_monitor.config import Settings
from seo_monitor.models import AuditReport, Severity
from seo_monitor.webhook import WebhookNotifier


@respx.mock
async def test_webhook_is_compact_and_signed() -> None:
    route = respx.post("https://hooks.example.test/seo").mock(return_value=Response(204))
    settings = Settings(
        webhook_url="https://hooks.example.test/seo",
        webhook_secret="signing-secret",
        allow_private_hosts=True,
    )
    now = datetime.now(UTC)
    report = AuditReport(
        id="audit-1",
        root_url="https://example.test/",
        started_at=now,
        completed_at=now,
        score=88,
        pages_scanned=2,
        issue_summary={severity: 0 for severity in Severity},
        pages=[],
    )

    await WebhookNotifier(settings).send(report)

    request = route.calls[0].request
    expected = hmac.new(
        b"signing-secret",
        request.content,
        hashlib.sha256,
    ).hexdigest()
    assert request.headers["X-SEO-Signature"] == f"sha256={expected}"
    assert b'"event":"audit.completed"' in request.content
    assert b'"pages"' not in request.content
