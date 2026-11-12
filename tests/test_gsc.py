from datetime import date

from seo_monitor import gsc
from seo_monitor.config import Settings
from seo_monitor.gsc import GSCClient
from seo_monitor.models import GSCFilter, GSCQuery


def test_gsc_query_builds_advanced_payload(monkeypatch) -> None:
    captured = {}

    class Request:
        def execute(self):
            return {"rows": [], "responseAggregationType": "byPage"}

    class SearchAnalytics:
        def query(self, *, siteUrl, body):
            captured["site_url"] = siteUrl
            captured["body"] = body
            return Request()

    class Service:
        def searchanalytics(self):
            return SearchAnalytics()

    monkeypatch.setattr(gsc, "build", lambda *args, **kwargs: Service())
    client = GSCClient(Settings())
    monkeypatch.setattr(client, "_credentials", lambda: object())
    query = GSCQuery(
        site_url="https://example.com/",
        start_date=date(2026, 11, 1),
        end_date=date(2026, 11, 7),
        search_type="image",
        aggregation_type="byPage",
        data_state="all",
        start_row=25,
        filters=[
            GSCFilter(
                dimension="query",
                operator="contains",
                expression="seo",
            )
        ],
    )

    result = client._query_sync(query)

    assert captured["body"]["type"] == "image"
    assert captured["body"]["startRow"] == 25
    assert captured["body"]["dimensionFilterGroups"][0]["filters"][0] == {
        "dimension": "query",
        "operator": "contains",
        "expression": "seo",
    }
    assert result.response_aggregation_type == "byPage"
