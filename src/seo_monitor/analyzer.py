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

    canonical_tag = soup.find("link", attrs={"rel": lambda rel: rel and "canonical" in rel})
    canonical = None
    if canonical_tag and canonical_tag.get("href"):
        canonical = resolve_link(page.final_url, str(canonical_tag["href"]))

    if page.status_code >= 500:
        issues.append(_issue("http.server_error", "availability", Severity.CRITICAL, "Page returned a server error", status=page.status_code))
    elif page.status_code >= 400:
        issues.append(_issue("http.client_error", "availability", Severity.ERROR, "Page returned a client error", status=page.status_code))

    if page.content_type and "html" not in page.content_type.lower():
        issues.append(_issue("content.non_html", "content", Severity.WARNING, "Response does not advertise HTML content", content_type=page.content_type))

    if not title:
        issues.append(_issue("title.missing", "metadata", Severity.ERROR, "Page has no title"))
    elif len(title) < 30:
        issues.append(_issue("title.short", "metadata", Severity.WARNING, "Title is shorter than 30 characters", length=len(title)))
    elif len(title) > 60:
        issues.append(_issue("title.long", "metadata", Severity.WARNING, "Title is longer than 60 characters", length=len(title)))

    if not description:
        issues.append(_issue("description.missing", "metadata", Severity.WARNING, "Page has no meta description"))
    elif not 70 <= len(description) <= 160:
        issues.append(_issue("description.length", "metadata", Severity.INFO, "Meta description is outside the 70–160 character guideline", length=len(description)))

    if not h1:
        issues.append(_issue("h1.missing", "content", Severity.ERROR, "Page has no H1 heading"))
    elif len(h1) > 1:
        issues.append(_issue("h1.multiple", "content", Severity.WARNING, "Page has multiple H1 headings", count=len(h1)))

    if not canonical:
        issues.append(_issue("canonical.missing", "indexability", Severity.INFO, "Page has no canonical link"))

    html_tag = soup.find("html")
    if not html_tag or not html_tag.get("lang"):
        issues.append(_issue("html.lang_missing", "accessibility", Severity.INFO, "HTML language is not declared"))

    robots = soup.find("meta", attrs={"name": re.compile(r"^robots$", re.I)})
    robots_content = str(robots.get("content", "")).lower() if robots else ""
    if "noindex" in robots_content:
        issues.append(_issue("robots.noindex", "indexability", Severity.WARNING, "Page asks search engines not to index it"))

    images = soup.find_all("img")
    images_without_alt = sum(1 for image in images if image.get("alt") is None)
    if images_without_alt:
        issues.append(_issue("image.alt_missing", "accessibility", Severity.WARNING, "Some images have no alt attribute", count=images_without_alt))

    for node in soup(["script", "style", "noscript", "template"]):
        node.decompose()
    word_count = len(re.findall(r"\b[\w'-]+\b", soup.get_text(" ", strip=True)))
    if word_count < 200 and page.status_code < 400:
        issues.append(_issue("content.thin", "content", Severity.WARNING, "Page contains fewer than 200 words", words=word_count))

    discovered_links: list[str] = []
    internal_links = 0
    external_links = 0
    for anchor in soup.find_all("a", href=True):
        resolved = resolve_link(page.final_url, str(anchor["href"]))
        if not resolved:
            continue
        if same_origin(page.final_url, resolved):
            internal_links += 1
            discovered_links.append(resolved)
        else:
            external_links += 1

    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            issues.append(_issue("structured_data.invalid_json", "structured_data", Severity.WARNING, "JSON-LD block is not valid JSON"))

    audit = PageAudit(
        url=page.requested_url,
        final_url=page.final_url,
        status_code=page.status_code,
        content_type=page.content_type,
        title=title,
        meta_description=description,
        h1=h1,
        canonical=canonical,
        word_count=word_count,
        internal_links=internal_links,
        external_links=external_links,
        images=len(images),
        images_without_alt=images_without_alt,
        duration_ms=page.duration_ms,
        issues=issues,
    )
    return AnalysisResult(audit=audit, discovered_links=list(dict.fromkeys(discovered_links)))

