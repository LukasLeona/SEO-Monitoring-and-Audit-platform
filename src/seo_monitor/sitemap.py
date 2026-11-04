from collections import deque
from urllib.parse import urlsplit, urlunsplit

from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException

from seo_monitor.config import Settings
from seo_monitor.fetcher import FetchError, HTTPFetcher
from seo_monitor.security import normalize_url, same_origin


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


class SitemapLoader:
    def __init__(self, settings: Settings) -> None:
        self.fetcher = HTTPFetcher(settings)

    async def discover(
        self,
        root_url: str,
        declared_sitemaps: list[str],
        *,
        max_urls: int,
        max_documents: int = 10,
    ) -> list[str]:
        parsed_root = urlsplit(normalize_url(root_url))
        default_sitemap = urlunsplit(
            (parsed_root.scheme, parsed_root.netloc, "/sitemap.xml", "", "")
        )
        candidates = declared_sitemaps or [default_sitemap]
        queue: deque[str] = deque(candidates)
        visited: set[str] = set()
        urls: list[str] = []

        while queue and len(visited) < max_documents and len(urls) < max_urls:
            candidate = queue.popleft()
            try:
                sitemap_url = normalize_url(candidate)
                if not same_origin(root_url, sitemap_url) or sitemap_url in visited:
                    continue
                visited.add(sitemap_url)
                response = await self.fetcher.fetch(sitemap_url)
                if response.status_code >= 400:
                    continue
                root = ElementTree.fromstring(response.html)
            except (
                DefusedXmlException,
                ElementTree.ParseError,
                FetchError,
                ValueError,
            ):
                continue

            locations = [
                (node.text or "").strip()
                for node in root.iter()
                if _local_name(node.tag) == "loc" and (node.text or "").strip()
            ]
            if _local_name(root.tag) == "sitemapindex":
                queue.extend(locations)
                continue

            for location in locations:
                try:
                    page_url = normalize_url(location)
                except ValueError:
                    continue
                if same_origin(root_url, page_url) and page_url not in urls:
                    urls.append(page_url)
                    if len(urls) >= max_urls:
                        break

        return urls
