import json
import re
from dataclasses import dataclass

from bs4 import BeautifulSoup

from seo_monitor.fetcher import FetchedPage
from seo_monitor.models import AuditIssue, PageAudit, Severity
from seo_monitor.security import resolve_link, same_origin


@dataclass(slots=True)
class AnalysisResult:
    audit: PageAudit
    discovered_links: list[str]


def _text(value: str | None) -> str | None:
    cleaned = " ".join(value.split()) if value else ""
    return cleaned or None


def _issue(
    code: str,
    category: str,
    severity: Severity,
    message: str,
    **evidence: object,
) -> AuditIssue:
    return AuditIssue(
        code=code,
        category=category,
        severity=severity,
        message=message,
        evidence=evidence,
    )


def analyze_page(page: FetchedPage) -> AnalysisResult:
    soup = BeautifulSoup(page.html, "html.parser")
    issues: list[AuditIssue] = []

    title = _text(soup.title.get_text(" ", strip=True)) if soup.title else None
    description_tag = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
    description = _text(description_tag.get("content")) if description_tag else None
    h1 = [_text(tag.get_text(" ", strip=True)) for tag in soup.find_all("h1")]
    h1 = [value for value in h1 if value]
    headings = [tag.name for tag in soup.find_all(re.compile(r"^h[1-6]$"))]
    heading_levels = [int(heading[1]) for heading in headings]

    canonical_tags = soup.find_all("link", attrs={"rel": lambda rel: rel and "canonical" in rel})
    canonical_tag = canonical_tags[0] if canonical_tags else None
    canonical = None
    if canonical_tag and canonical_tag.get("href"):
        canonical = resolve_link(page.final_url, str(canonical_tag["href"]))
    if len(canonical_tags) > 1:
        issues.append(
            _issue(
                "canonical.multiple",
                "indexability",
                Severity.ERROR,
                "Page declares more than one canonical URL",
                count=len(canonical_tags),
            )
        )

    if page.status_code >= 500:
        issues.append(
            _issue(
                "http.server_error",
                "availability",
                Severity.CRITICAL,
                "Page returned a server error",
                status=page.status_code,
            )
        )
    elif page.status_code >= 400:
        issues.append(
            _issue(
                "http.client_error",
                "availability",
                Severity.ERROR,
                "Page returned a client error",
                status=page.status_code,
            )
        )

    if page.content_type and "html" not in page.content_type.lower():
        issues.append(
            _issue(
                "content.non_html",
                "content",
                Severity.WARNING,
                "Response does not advertise HTML content",
                content_type=page.content_type,
            )
        )

    if not title:
        issues.append(_issue("title.missing", "metadata", Severity.ERROR, "Page has no title"))
    elif len(title) < 30:
        issues.append(
            _issue(
                "title.short",
                "metadata",
                Severity.WARNING,
                "Title is shorter than 30 characters",
                length=len(title),
            )
        )
    elif len(title) > 60:
        issues.append(
            _issue(
                "title.long",
                "metadata",
                Severity.WARNING,
                "Title is longer than 60 characters",
                length=len(title),
            )
        )

    if not description:
        issues.append(
            _issue(
                "description.missing", "metadata", Severity.WARNING, "Page has no meta description"
            )
        )
    elif not 70 <= len(description) <= 160:
        issues.append(
            _issue(
                "description.length",
                "metadata",
                Severity.INFO,
                "Meta description is outside the 70–160 character guideline",
                length=len(description),
            )
        )

    if not h1:
        issues.append(_issue("h1.missing", "content", Severity.ERROR, "Page has no H1 heading"))
    elif len(h1) > 1:
        issues.append(
            _issue(
                "h1.multiple",
                "content",
                Severity.WARNING,
                "Page has multiple H1 headings",
                count=len(h1),
            )
        )

    for previous, current in zip(heading_levels, heading_levels[1:], strict=False):
        if current > previous + 1:
            issues.append(
                _issue(
                    "heading.skipped_level",
                    "content",
                    Severity.WARNING,
                    "Heading hierarchy skips one or more levels",
                    from_level=previous,
                    to_level=current,
                )
            )
            break

    if not canonical:
        issues.append(
            _issue("canonical.missing", "indexability", Severity.INFO, "Page has no canonical link")
        )
    elif page.final_url.startswith("https://") and canonical.startswith("http://"):
        issues.append(
            _issue(
                "canonical.insecure",
                "indexability",
                Severity.WARNING,
                "HTTPS page points to an HTTP canonical URL",
                canonical=canonical,
            )
        )

    html_tag = soup.find("html")
    if not html_tag or not html_tag.get("lang"):
        issues.append(
            _issue(
                "html.lang_missing", "accessibility", Severity.INFO, "HTML language is not declared"
            )
        )

    robots = soup.find("meta", attrs={"name": re.compile(r"^robots$", re.I)})
    robots_content = str(robots.get("content", "")).lower() if robots else ""
    if "noindex" in robots_content:
        issues.append(
            _issue(
                "robots.noindex",
                "indexability",
                Severity.WARNING,
                "Page asks search engines not to index it",
            )
        )

    viewport = soup.find("meta", attrs={"name": re.compile(r"^viewport$", re.I)})
    if not viewport:
        issues.append(
            _issue(
                "mobile.viewport_missing",
                "mobile",
                Severity.WARNING,
                "Page has no viewport meta tag",
            )
        )

    open_graph = soup.find("meta", attrs={"property": re.compile(r"^og:", re.I)})
    if not open_graph:
        issues.append(
            _issue(
                "social.open_graph_missing",
                "social",
                Severity.INFO,
                "Page has no Open Graph metadata",
            )
        )

    twitter_card = soup.find("meta", attrs={"name": re.compile(r"^twitter:card$", re.I)})
    if not twitter_card:
        issues.append(
            _issue(
                "social.twitter_card_missing",
                "social",
                Severity.INFO,
                "Page has no Twitter card metadata",
            )
        )

    hreflang_tags = soup.find_all(
        "link", attrs={"rel": lambda rel: rel and "alternate" in rel, "hreflang": True}
    )
    hreflang_values: list[str] = []
    invalid_hreflang = 0
    for tag in hreflang_tags:
        value = str(tag.get("hreflang", "")).strip().lower()
        target = resolve_link(page.final_url, str(tag.get("href", "")))
        if not value or not target:
            invalid_hreflang += 1
            continue
        hreflang_values.append(value)
    if invalid_hreflang:
        issues.append(
            _issue(
                "hreflang.invalid",
                "international",
                Severity.WARNING,
                "Some hreflang entries are incomplete or invalid",
                count=invalid_hreflang,
            )
        )
    duplicates = sorted(value for value in set(hreflang_values) if hreflang_values.count(value) > 1)
    if duplicates:
        issues.append(
            _issue(
                "hreflang.duplicate",
                "international",
                Severity.WARNING,
                "Page declares duplicate hreflang values",
                values=duplicates,
            )
        )
    if hreflang_values and "x-default" not in hreflang_values:
        issues.append(
            _issue(
                "hreflang.x_default_missing",
                "international",
                Severity.INFO,
                "Hreflang set does not include x-default",
            )
        )

    images = soup.find_all("img")
    images_without_alt = sum(1 for image in images if image.get("alt") is None)
    if images_without_alt:
        issues.append(
            _issue(
                "image.alt_missing",
                "accessibility",
                Severity.WARNING,
                "Some images have no alt attribute",
                count=images_without_alt,
            )
        )

    discovered_links: list[str] = []
    internal_links = 0
    external_links = 0
    empty_links = 0
    for anchor in soup.find_all("a", href=True):
        accessible_name = (
            anchor.get_text(" ", strip=True)
            or anchor.get("aria-label")
            or next(
                (image.get("alt") for image in anchor.find_all("img") if image.get("alt")),
                None,
            )
        )
        if not accessible_name:
            empty_links += 1
        resolved = resolve_link(page.final_url, str(anchor["href"]))
        if not resolved:
            continue
        if same_origin(page.final_url, resolved):
            internal_links += 1
            discovered_links.append(resolved)
        else:
            external_links += 1

    if empty_links:
        issues.append(
            _issue(
                "link.empty_text",
                "accessibility",
                Severity.WARNING,
                "Some links have no descriptive text or accessible label",
                count=empty_links,
            )
        )

    structured_data_types: list[str] = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(script.string or "")
            entries = data if isinstance(data, list) else [data]
            for entry in entries:
                if isinstance(entry, dict) and entry.get("@type"):
                    value = entry["@type"]
                    types = value if isinstance(value, list) else [value]
                    structured_data_types.extend(str(item) for item in types)
        except (json.JSONDecodeError, TypeError):
            issues.append(
                _issue(
                    "structured_data.invalid_json",
                    "structured_data",
                    Severity.WARNING,
                    "JSON-LD block is not valid JSON",
                )
            )

    for node in soup(["script", "style", "noscript", "template"]):
        node.decompose()
    word_count = len(re.findall(r"\b[\w'-]+\b", soup.get_text(" ", strip=True)))
    if word_count < 200 and page.status_code < 400:
        issues.append(
            _issue(
                "content.thin",
                "content",
                Severity.WARNING,
                "Page contains fewer than 200 words",
                words=word_count,
            )
        )

    audit = PageAudit(
        url=page.requested_url,
        final_url=page.final_url,
        status_code=page.status_code,
        content_type=page.content_type,
        title=title,
        meta_description=description,
        h1=h1,
        headings=headings,
        canonical=canonical,
        meta_robots=robots_content or None,
        has_viewport=viewport is not None,
        has_open_graph=open_graph is not None,
        has_twitter_card=twitter_card is not None,
        hreflang_count=len(hreflang_tags),
        hreflang_values=list(dict.fromkeys(hreflang_values)),
        structured_data_types=list(dict.fromkeys(structured_data_types)),
        word_count=word_count,
        internal_links=internal_links,
        external_links=external_links,
        empty_links=empty_links,
        images=len(images),
        images_without_alt=images_without_alt,
        duration_ms=page.duration_ms,
        issues=issues,
    )
    return AnalysisResult(audit=audit, discovered_links=list(dict.fromkeys(discovered_links)))
