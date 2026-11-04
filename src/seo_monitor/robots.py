from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

from seo_monitor.config import Settings
from seo_monitor.fetcher import FetchError, HTTPFetcher


@dataclass(slots=True)
class RobotsPolicy:
    parser: RobotFileParser
    user_agent: str
    sitemaps: list[str]
    crawl_delay: float | None
    available: bool

    def can_fetch(self, url: str) -> bool:
        return self.parser.can_fetch(self.user_agent, url)

    @classmethod
    async def load(cls, root_url: str, settings: Settings) -> "RobotsPolicy":
        parsed = urlsplit(root_url)
        robots_url = urlunsplit((parsed.scheme, parsed.netloc, "/robots.txt", "", ""))
        user_agent = settings.user_agent.split("/", 1)[0]
        parser = RobotFileParser()
        parser.set_url(robots_url)

        try:
            response = await HTTPFetcher(settings).fetch(robots_url)
        except FetchError:
            parser.parse([])
            return cls(parser, user_agent, [], None, False)

        if response.status_code >= 400:
            parser.parse([])
            return cls(parser, user_agent, [], None, False)

        lines = response.html.splitlines()
        parser.parse(lines)
        sitemap_lines = [line.strip() for line in lines]
        sitemaps = [
            line.split(":", 1)[1].strip()
            for line in sitemap_lines
            if line.lower().startswith("sitemap:") and line.split(":", 1)[1].strip()
        ]
        delay = parser.crawl_delay(user_agent) or parser.crawl_delay("*")
        return cls(
            parser=parser,
            user_agent=user_agent,
            sitemaps=sitemaps,
            crawl_delay=min(float(delay), 30.0) if delay else None,
            available=True,
        )
