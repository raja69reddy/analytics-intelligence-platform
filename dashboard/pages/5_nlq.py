"""Ask Your Data — Natural Language Query page."""

import os
import sys
import time

import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

st.set_page_config(page_title="Ask Your Data", page_icon="💬", layout="wide")

st.title("💬 Ask Your Data")
st.markdown(
    "Type any question about your analytics data and the AI will generate "
    "the SQL, run it, and show you the results."
)

EXAMPLE_QUESTIONS = [
    "Top 5 channels by sessions",
    "Pages with highest bounce rate",
    "Daily traffic last 30 days",
    "Conversion rate by channel",
]

# ── Example question buttons ──────────────────────────────────────────────────
st.subheader("Example Questions")
cols = st.columns(len(EXAMPLE_QUESTIONS))
for col, example in zip(cols, EXAMPLE_QUESTIONS):
    if col.button(example, use_container_width=True):
        st.session_state["nlq_question"] = example

# ── Question input ────────────────────────────────────────────────────────────
question = st.text_area(
    "Your question:",
    value=st.session_state.get("nlq_question", ""),
    height=80,
    placeholder='e.g. "What are the top 5 channels by total sessions?"',
    key="nlq_question_area",
)

ask_col, _ = st.columns([1, 5])
run_query = ask_col.button("🔍 Ask AI", type="primary", use_container_width=True)

# ── Query history (last 5) ────────────────────────────────────────────────────
if "nlq_history" not in st.session_state:
    st.session_state["nlq_history"] = []

# ── Run the query ─────────────────────────────────────────────────────────────
if run_query and question.strip():
    st.divider()

    with st.spinner("Thinking…"):
        start = time.time()
        try:
            from ai.nlq.nlq_engine import NLQEngine

            engine = NLQEngine()
            result = engine.ask(question)
        except Exception as exc:
            st.error(f"Engine error: {exc}")
            st.stop()

    if result["error"]:
        st.error(f"**Error:** {result['error']}")
    else:
        # ── Generated SQL ─────────────────────────────────────────────────────
        st.subheader("Generated SQL")
        with st.expander("View SQL", expanded=True):
            st.code(result["sql"] or "(no SQL)", language="sql")

        # ── Results ───────────────────────────────────────────────────────────
        st.subheader("Results")
        df = result.get("data")
        if df is not None and not df.empty:
            st.dataframe(df, use_container_width=True, hide_index=True)

            # CSV download
            csv_bytes = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇ Download as CSV",
                data=csv_bytes,
                file_name="nlq_results.csv",
                mime="text/csv",
            )
        else:
            st.info("The query returned no rows.")

        cache_note = " _(from cache)_" if result["from_cache"] else ""
        st.caption(f"Completed in {result['execution_time_s']}s{cache_note}")

        # ── Update history ────────────────────────────────────────────────────
        history_entry = {
            "question": question,
            "sql": result["sql"],
            "rows": len(df) if df is not None else 0,
            "time_s": result["execution_time_s"],
        }
        history = st.session_state["nlq_history"]
        history = [e for e in history if e["question"] != question]
        history.insert(0, history_entry)
        st.session_state["nlq_history"] = history[:5]

elif run_query:
    st.warning("Please enter a question.")

# ── Query history ──────────────────────────────────────────────────────────────
if st.session_state["nlq_history"]:
    st.divider()
    st.subheader("Recent Questions (last 5)")
    for entry in st.session_state["nlq_history"]:
        with st.expander(f"❓ {entry['question']}", expanded=False):
            st.code(entry["sql"] or "(no SQL)", language="sql")
            st.caption(f"{entry['rows']} row(s) | {entry['time_s']}s")
