from seo_monitor.models import AuditJobStatus, SystemStats


def render_metrics(stats: SystemStats) -> str:
    lines = [
        "# HELP seo_audits_total Stored SEO audit reports.",
        "# TYPE seo_audits_total gauge",
        f"seo_audits_total {stats.audits_total}",
        "# HELP seo_jobs_total Stored audit jobs by status.",
        "# TYPE seo_jobs_total gauge",
    ]
    for status in AuditJobStatus:
        count = stats.jobs_by_status.get(status, 0)
        lines.append(f'seo_jobs_total{{status="{status}"}} {count}')
    lines.extend(
        [
            "# HELP seo_monitors_total Configured recurring monitors.",
            "# TYPE seo_monitors_total gauge",
            f"seo_monitors_total {stats.monitors_total}",
            "# HELP seo_monitors_enabled Enabled recurring monitors.",
            "# TYPE seo_monitors_enabled gauge",
            f"seo_monitors_enabled {stats.monitors_enabled}",
            "# HELP seo_schema_version Applied database schema version.",
            "# TYPE seo_schema_version gauge",
            f"seo_schema_version {stats.schema_version}",
            "",
        ]
    )
    return "\n".join(lines)
