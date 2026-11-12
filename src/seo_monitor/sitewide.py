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
    return [score_page(page) for page in pages]
