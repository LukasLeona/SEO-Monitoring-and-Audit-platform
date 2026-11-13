from collections import defaultdict
from collections.abc import Callable

from seo_monitor.models import AuditIssue, PageAudit, Severity
from seo_monitor.scoring import score_page


def _flag_duplicates(
    pages: list[PageAudit],
    *,
    value_for: Callable[[PageAudit], str | None],
    code: str,
    message: str,
) -> None:
    groups: dict[str, list[PageAudit]] = defaultdict(list)
    for page in pages:
        value = value_for(page)
        if value and page.status_code < 400:
            groups[value.casefold()].append(page)

    for duplicates in groups.values():
        if len(duplicates) < 2:
            continue
        urls = [page.final_url for page in duplicates]
        for page in duplicates:
            page.issues.append(
                AuditIssue(
                    code=code,
                    category="sitewide",
                    severity=Severity.WARNING,
                    message=message,
                    evidence={"duplicate_urls": urls},
                )
            )


def apply_sitewide_checks(pages: list[PageAudit]) -> list[PageAudit]:
    _flag_duplicates(
        pages,
        value_for=lambda page: page.title,
        code="sitewide.duplicate_title",
        message="Multiple pages use the same title",
    )
    _flag_duplicates(
        pages,
        value_for=lambda page: page.meta_description,
        code="sitewide.duplicate_description",
        message="Multiple pages use the same meta description",
    )
    _flag_duplicates(
        pages,
        value_for=lambda page: page.content_hash if page.word_count >= 50 else None,
        code="sitewide.duplicate_content",
        message="Multiple pages contain substantially identical visible content",
    )
    pages_by_url = {page.final_url: page for page in pages}
    inbound_counts = {url: 0 for url in pages_by_url}
    for source in pages:
        for target in set(source.internal_link_targets):
            if target in inbound_counts:
                inbound_counts[target] += 1

    for page in pages:
        page.inbound_internal_links = inbound_counts.get(page.final_url, 0)
        broken_targets = sorted(
            target
            for target in page.internal_link_targets
            if target in pages_by_url and pages_by_url[target].status_code >= 400
        )
        if broken_targets:
            page.issues.append(
                AuditIssue(
                    code="link.broken_internal",
                    category="links",
                    severity=Severity.ERROR,
                    message="Page links to an internal URL returning an error",
                    evidence={"targets": broken_targets},
                )
            )
        if (
            page.crawl_depth > 0
            and 200 <= page.status_code < 300
            and page.inbound_internal_links == 0
        ):
            page.issues.append(
                AuditIssue(
                    code="sitewide.orphan_page",
                    category="sitewide",
                    severity=Severity.WARNING,
                    message="Page has no inbound links from other crawled pages",
                    evidence={"discovered_from": page.discovered_from},
                )
            )
    return [score_page(page) for page in pages]
