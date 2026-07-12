"""AI Generated Reports page."""

import os
import sys
from datetime import datetime
from pathlib import Path

import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

REPORTS_DIR = (
    Path(__file__).resolve().parent.parent.parent / "data" / "processed" / "reports"
)

st.set_page_config(page_title="AI Generated Reports", page_icon="📋", layout="wide")

st.title("📋 AI Generated Reports")
st.markdown(
    "Generate AI-powered executive summaries of your analytics data. "
    "Each report covers Traffic, Behavior, Conversions, and SEO."
)


def _list_reports() -> list[Path]:
    """Return saved report files sorted newest-first."""
    if not REPORTS_DIR.exists():
        return []
    return sorted(REPORTS_DIR.glob("report_*.md"), reverse=True)


def _load_report(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ── Generate new report ───────────────────────────────────────────────────────
st.subheader("Generate New Report")

gen_col, _ = st.columns([1, 4])
generate = gen_col.button(
    "Generate New Report", type="primary", use_container_width=True
)

if generate:
    with st.spinner("Generating AI report — this may take up to 60 seconds..."):
        try:
            from ai.report_generation.generator import ReportGenerator
            from ai.report_generation.formatter import save_report

            generator = ReportGenerator()
            report = generator.generate_full_report()
            path = save_report(report)
            st.success(f"Report generated and saved: `{path.name}`")
            st.session_state["latest_report_path"] = str(path)
            st.session_state["latest_report_time"] = report["generated_at"]
        except EnvironmentError as exc:
            st.error(f"**Configuration error:** {exc}")
            st.info(
                "Add `OPENAI_API_KEY` to your `.env` file to enable AI report generation."
            )
        except Exception as exc:
            st.error(f"**Error generating report:** {exc}")

st.divider()

# ── Latest report ─────────────────────────────────────────────────────────────
reports = _list_reports()

if reports:
    latest = reports[0]
    mtime = datetime.fromtimestamp(latest.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")

    st.subheader("Latest Report")
    st.caption(f"Generated: {mtime} | File: `{latest.name}`")

    content = _load_report(latest)
    st.markdown(content)

    dl_col, _ = st.columns([1, 5])
    dl_col.download_button(
        "Download Report (Markdown)",
        data=content.encode("utf-8"),
        file_name=latest.name,
        mime="text/markdown",
        use_container_width=True,
    )

    # PDF placeholder
    st.info(
        "PDF export: install `weasyprint` and run `pip install weasyprint` to enable PDF download."
    )

    st.divider()

    # ── Report history ─────────────────────────────────────────────────────────
    if len(reports) > 1:
        st.subheader("Report History (last 5)")
        for report_path in reports[1:6]:
            ts = datetime.fromtimestamp(report_path.stat().st_mtime).strftime(
                "%Y-%m-%d %H:%M"
            )
            with st.expander(f"Report: {report_path.name}  ({ts})", expanded=False):
                st.markdown(_load_report(report_path))
                st.download_button(
                    "Download",
                    data=_load_report(report_path).encode("utf-8"),
                    file_name=report_path.name,
                    mime="text/markdown",
                    key=f"dl_{report_path.name}",
                )
else:
    st.info(
        "No reports generated yet. Click **Generate New Report** above to create your first report."
    )

st.divider()

# ── Email placeholder ──────────────────────────────────────────────────────────
st.subheader("Email Report")
st.markdown(
    "_Email report delivery is coming soon. Configure SMTP credentials in `.env` to enable._"
)
