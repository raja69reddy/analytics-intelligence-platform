"""Pipeline Monitor dashboard page."""
import os
import sys
import subprocess
from datetime import datetime

import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from utils.db import query_df
from utils.pipeline_monitor import (
    get_pipeline_history,
    get_pipeline_stats,
    log_pipeline_run,
)

st.set_page_config(page_title="Pipeline Monitor", page_icon="⚙️", layout="wide")
st.title("⚙️ Pipeline Monitor")

# ── DB guard ──────────────────────────────────────────────────────────────────
try:
    query_df("SELECT 1 AS ok")
except Exception as exc:
    st.error(f"Database connection failed: {exc}")
    st.stop()

# ── Row counts for all raw tables ─────────────────────────────────────────────
PIPELINE_TABLES = {
    "ga4":         "raw_ga4_sessions",
    "server_logs": "raw_server_logs",
    "clickstream": "raw_clickstream_events",
    "scraper":     "raw_scrape_pages",
}


@st.cache_data(ttl=60)
def _load_table_counts() -> dict:
    counts = {}
    for name, table in PIPELINE_TABLES.items():
        try:
            df = query_df(
                f"SELECT COUNT(*) AS n, MAX(ingested_at) AS last_ingest FROM {table}"
            )
            counts[name] = {
                "table":       table,
                "rows":        int(df["n"].iloc[0]),
                "last_ingest": str(df["last_ingest"].iloc[0])[:19],
            }
        except Exception as exc:
            counts[name] = {"table": table, "rows": 0, "last_ingest": "error", "error": str(exc)}
    return counts


st.subheader("Table Row Counts & Last Ingest")
with st.spinner("Querying table stats..."):
    table_counts = _load_table_counts()

cols = st.columns(4)
for i, (name, info) in enumerate(table_counts.items()):
    with cols[i]:
        rows = info.get("rows", 0)
        last = info.get("last_ingest", "—")
        st.metric(label=f"{name}", value=f"{rows:,} rows")
        st.caption(f"Last ingest: {last}")

st.divider()

# ── Pipeline run history ───────────────────────────────────────────────────────
st.subheader("Pipeline Run History")

history = get_pipeline_history(limit=20)
if not history:
    st.info("No pipeline runs logged yet. Run a pipeline to see history.")
else:
    import pandas as pd

    history_df = pd.DataFrame(history)
    history_df = history_df[["timestamp", "name", "status", "rows", "duration_s"]]
    history_df = history_df.rename(columns={
        "timestamp":  "Run Time",
        "name":       "Pipeline",
        "status":     "Status",
        "rows":       "Rows",
        "duration_s": "Duration (s)",
    })

    def _status_color(row):
        color = (
            "#d4edda" if row["Status"] == "success"
            else "#f8d7da" if str(row["Status"]).startswith("error")
            else "#fff3cd"
        )
        return [f"background-color: {color}"] * len(row)

    styled = history_df.style.apply(_status_color, axis=1)
    st.dataframe(styled, use_container_width=True, hide_index=True)

st.divider()

# ── Pipeline stats ─────────────────────────────────────────────────────────────
st.subheader("Pipeline Statistics")
stats = get_pipeline_stats()
if stats:
    stats_rows = [
        {
            "Pipeline":       name,
            "Total Runs":     s["total_runs"],
            "Success Rate":   f"{s['success_rate_pct']}%",
            "Avg Duration":   f"{s['avg_duration_s']}s",
        }
        for name, s in stats.items()
    ]
    import pandas as pd
    st.dataframe(pd.DataFrame(stats_rows), use_container_width=True, hide_index=True)
else:
    st.info("No stats available yet.")

st.divider()

# ── Run pipelines ─────────────────────────────────────────────────────────────
st.subheader("Run Pipelines")

col_a, col_b = st.columns(2)

with col_a:
    st.markdown("**Run All Pipelines**")
    if st.button("▶ Run All Pipelines (Full Mode)", type="primary"):
        import sys as _sys
        from pathlib import Path as _Path
        run_all_script = str(_Path(__file__).resolve().parent.parent.parent / "ingestion" / "run_all.py")
        with st.spinner("Running all pipelines..."):
            try:
                result = subprocess.run(
                    [_sys.executable, run_all_script, "--mode", "full"],
                    capture_output=True, text=True, timeout=300,
                )
                if result.returncode == 0:
                    st.success("All pipelines completed successfully.")
                    st.code(result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout)
                    _load_table_counts.clear()
                else:
                    st.error("Pipeline run failed.")
                    st.code(result.stderr[-2000:])
            except subprocess.TimeoutExpired:
                st.error("Pipeline timed out after 5 minutes.")
            except Exception as exc:
                st.error(f"Error launching pipeline: {exc}")

with col_b:
    st.markdown("**Run Single Pipeline**")
    selected = st.selectbox(
        "Choose pipeline",
        options=["ga4", "server_logs", "clickstream", "scraper"],
        key="single_pipeline_select",
    )
    if st.button(f"▶ Run {selected}", key="run_single"):
        import sys as _sys
        from pathlib import Path as _Path
        run_all_script = str(_Path(__file__).resolve().parent.parent.parent / "ingestion" / "run_all.py")
        with st.spinner(f"Running {selected}..."):
            try:
                result = subprocess.run(
                    [_sys.executable, run_all_script, "--mode", "full", "--pipeline", selected],
                    capture_output=True, text=True, timeout=120,
                )
                if result.returncode == 0:
                    st.success(f"{selected} pipeline completed.")
                    st.code(result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout)
                    _load_table_counts.clear()
                else:
                    st.error(f"{selected} pipeline failed.")
                    st.code(result.stderr[-2000:])
            except subprocess.TimeoutExpired:
                st.error("Pipeline timed out.")
            except Exception as exc:
                st.error(f"Error: {exc}")
