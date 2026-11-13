import asyncio
from typing import Any

import google.auth
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from seo_monitor.config import Settings
from seo_monitor.models import (
    GSCQuery,
    GSCResponse,
    GSCRow,
    URLInspectionRequest,
    URLInspectionResponse,
)

GSC_READONLY_SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"


class GSCError(RuntimeError):
    pass


class GSCClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _credentials(self) -> Any:
        if self.settings.gsc_credentials_file:
            return service_account.Credentials.from_service_account_file(
                self.settings.gsc_credentials_file,
                scopes=[GSC_READONLY_SCOPE],
            )
        credentials, _ = google.auth.default(scopes=[GSC_READONLY_SCOPE])
        return credentials

    def _query_sync(self, query: GSCQuery) -> GSCResponse:
        try:
            service = build(
                "searchconsole",
                "v1",
                credentials=self._credentials(),
                cache_discovery=False,
            )
            payload = {
                "startDate": query.start_date.isoformat(),
                "endDate": query.end_date.isoformat(),
                "dimensions": query.dimensions,
                "type": query.search_type,
                "aggregationType": query.aggregation_type,
                "dataState": query.data_state,
                "rowLimit": query.row_limit,
                "startRow": query.start_row,
            }
            if query.filters:
                payload["dimensionFilterGroups"] = [
                    {
                        "groupType": "and",
                        "filters": [item.model_dump() for item in query.filters],
                    }
                ]
            response = (
                service.searchanalytics().query(siteUrl=query.site_url, body=payload).execute()
            )
        except (HttpError, OSError, ValueError, google.auth.exceptions.GoogleAuthError) as exc:
            raise GSCError(f"Search Console request failed: {exc}") from exc

        rows = [
            GSCRow(
                keys=row.get("keys", []),
                clicks=row.get("clicks", 0),
                impressions=row.get("impressions", 0),
                ctr=row.get("ctr", 0),
                position=row.get("position", 0),
            )
            for row in response.get("rows", [])
        ]
        return GSCResponse(
            site_url=query.site_url,
            rows=rows,
            response_aggregation_type=response.get("responseAggregationType"),
        )

    async def query(self, query: GSCQuery) -> GSCResponse:
        return await asyncio.to_thread(self._query_sync, query)

    def _inspect_sync(
        self,
        request: URLInspectionRequest,
    ) -> URLInspectionResponse:
        try:
            service = build(
                "searchconsole",
                "v1",
                credentials=self._credentials(),
                cache_discovery=False,
            )
            payload = {
                "inspectionUrl": str(request.inspection_url),
                "siteUrl": request.site_url,
                "languageCode": request.language_code,
            }
            response = service.urlInspection().index().inspect(body=payload).execute()
        except (
            HttpError,
            OSError,
            ValueError,
            google.auth.exceptions.GoogleAuthError,
        ) as exc:
            raise GSCError(f"URL Inspection request failed: {exc}") from exc
        return URLInspectionResponse(
            inspection_url=str(request.inspection_url),
            site_url=request.site_url,
            inspection_result=response.get("inspectionResult", {}),
        )

    async def inspect(
        self,
        request: URLInspectionRequest,
    ) -> URLInspectionResponse:
        return await asyncio.to_thread(self._inspect_sync, request)
