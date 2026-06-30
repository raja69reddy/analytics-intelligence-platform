"""Report formatting utilities — markdown, HTML, and file output."""
import os
from datetime import datetime
from pathlib import Path

REPORTS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "processed" / "reports"


def format_as_markdown(report: dict) -> str:
    """Format a report dict as a markdown document."""
    lines = [
        f"# Analytics Intelligence Report",
        f"**Generated:** {report.get('generated_at', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}",
        "",
        "---",
        "",
    ]

    if report.get("executive_summary"):
        lines += ["## Executive Summary", "", report["executive_summary"], "", "---", ""]

    section_map = {
        "traffic": "## Traffic & Sessions",
        "behavior": "## User Behavior",
        "conversions": "## Conversions",
        "seo": "## SEO & Content",
    }
    for key, heading in section_map.items():
        content = report.get(key)
        if content:
            lines += [heading, "", content, ""]

    return "\n".join(lines)


def format_as_html(report: dict) -> str:
    """Format a report dict as a minimal HTML document."""
    md = format_as_markdown(report)
    # Very simple conversion: wrap paragraphs in <p> tags
    body_lines = []
    for line in md.splitlines():
        if line.startswith("## "):
            body_lines.append(f"<h2>{line[3:]}</h2>")
        elif line.startswith("# "):
            body_lines.append(f"<h1>{line[2:]}</h1>")
        elif line.startswith("**") and line.endswith("**"):
            body_lines.append(f"<strong>{line[2:-2]}</strong>")
        elif line == "---":
            body_lines.append("<hr>")
        elif line.strip():
            body_lines.append(f"<p>{line}</p>")
        else:
            body_lines.append("")

    generated = report.get("generated_at", "")
    return (
        "<!DOCTYPE html>\n<html><head>"
        "<meta charset='utf-8'>"
        f"<title>Analytics Report {generated}</title>"
        "<style>body{{font-family:Arial,sans-serif;max-width:900px;margin:40px auto;line-height:1.6}}"
        "h1,h2{{color:#1a1a2e}}hr{{border:1px solid #eee}}</style>"
        "</head><body>\n"
        + "\n".join(body_lines)
        + "\n</body></html>"
    )


def add_charts_to_report(report: dict, charts: dict) -> dict:
    """Embed chart file references into a report dict.

    charts: mapping of section key → chart file path string
    """
    report = dict(report)
    report.setdefault("charts", {})
    report["charts"].update(charts)
    return report


def save_report(report: dict, filename: str | None = None) -> Path:
    """Save the report as a markdown file under data/processed/reports/.

    Returns the path to the saved file.
    """
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    if filename is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
        filename = f"report_{date_str}.md"
    path = REPORTS_DIR / filename
    path.write_text(format_as_markdown(report), encoding="utf-8")
    return path
