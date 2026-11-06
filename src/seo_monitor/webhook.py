import hashlib
import hmac
import json

import httpx

from seo_monitor.config import Settings
from seo_monitor.models import AuditReport
from seo_monitor.security import validate_public_url


class WebhookDeliveryError(RuntimeError):
    pass


class WebhookNotifier:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def send(self, report: AuditReport) -> None:
        if not self.settings.webhook_url:
            return

        try:
            url = await validate_public_url(
                self.settings.webhook_url,
                allow_private_hosts=self.settings.allow_private_hosts,
            )
            payload = {
                "event": "audit.completed",
                "audit_id": report.id,
                "root_url": report.root_url,
                "score": report.score,
                "pages_scanned": report.pages_scanned,
                "issue_summary": report.issue_summary,
                "completed_at": report.completed_at.isoformat(),
            }
            body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
            headers = {
                "Content-Type": "application/json",
                "User-Agent": self.settings.user_agent,
            }
            if self.settings.webhook_secret:
                secret = self.settings.webhook_secret.get_secret_value().encode()
                digest = hmac.new(secret, body, hashlib.sha256).hexdigest()
                headers["X-SEO-Signature"] = f"sha256={digest}"

            async with httpx.AsyncClient(
                timeout=self.settings.webhook_timeout_seconds,
                follow_redirects=False,
                trust_env=False,
            ) as client:
                response = await client.post(url, content=body, headers=headers)
                response.raise_for_status()
        except (httpx.HTTPError, ValueError) as exc:
            raise WebhookDeliveryError(f"webhook delivery failed: {exc}") from exc
