"""Tests for the EDA notebook and eda_reporter.py."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

NOTEBOOK_PATH = ROOT / "analysis" / "explore.ipynb"
EDA_PLOTS_DIR = ROOT / "data" / "processed" / "eda_plots"
PROCESSED_DIR = ROOT / "data" / "processed"


# ── Test 1: Notebook exists and has content ───────────────────────────────────

def test_notebook_exists():
    assert NOTEBOOK_PATH.exists(), f"explore.ipynb not found at {NOTEBOOK_PATH}"


def test_notebook_has_minimum_cells():
    nb = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    cell_count = len(nb["cells"])
    assert cell_count >= 50, f"Expected >= 50 cells, got {cell_count}"


def test_notebook_is_valid_json():
    try:
        nb = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
        assert "cells" in nb
        assert "metadata" in nb
        assert "nbformat" in nb
    except json.JSONDecodeError as e:
        pytest.fail(f"explore.ipynb is not valid JSON: {e}")


def test_notebook_has_markdown_sections():
    nb = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    md_cells = [c for c in nb["cells"] if c["cell_type"] == "markdown"]
    assert len(md_cells) >= 10, f"Expected >= 10 markdown cells, got {len(md_cells)}"


def test_notebook_has_expected_sections():
    nb = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    all_text = " ".join(
        "".join(c["source"])
        for c in nb["cells"]
        if c["cell_type"] == "markdown"
    )
    required_sections = [
        "Section 8",
        "Section 9",
        "Section 10",
        "Section 11",
        "Section 12",
        "Section 13",
        "Section 14",
        "Section 15",
    ]
    for section in required_sections:
        assert section in all_text, f"Missing '{section}' in notebook markdown"


def test_notebook_has_code_cells():
    nb = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    code_cells = [c for c in nb["cells"] if c["cell_type"] == "code"]
    assert len(code_cells) >= 30, f"Expected >= 30 code cells, got {len(code_cells)}"


# ── Test 2: eda_reporter.py runs without errors ───────────────────────────────

def test_eda_reporter_imports():
    from utils.eda_reporter import generate_report, _collect_metrics
    assert callable(generate_report)
    assert callable(_collect_metrics)


def test_eda_reporter_collect_metrics():
    from utils.eda_reporter import _collect_metrics
    m = _collect_metrics()
    assert isinstance(m, dict)
    required_keys = [
        "total_sessions", "avg_bounce_pct", "total_conv",
        "avg_cvr", "top_channel", "top_page", "top_device",
        "ga4_rows", "fct_s_rows", "fct_e_rows",
    ]
    for key in required_keys:
        assert key in m, f"Missing key '{key}' in metrics dict"


def test_eda_reporter_metrics_values():
    from utils.eda_reporter import _collect_metrics
    m = _collect_metrics()
    assert m["total_sessions"] > 0, "total_sessions should be > 0"
    assert 0 <= m["avg_bounce_pct"] <= 100, "avg_bounce_pct out of range"
    assert m["ga4_rows"] >= 2000, f"Expected >= 2000 GA4 rows, got {m['ga4_rows']}"
    assert m["fct_s_rows"] >= 2000, f"Expected >= 2000 fct_sessions rows"


def test_eda_reporter_generate_report(tmp_path, monkeypatch):
    """eda_reporter generates a report file."""
    from utils import eda_reporter
    monkeypatch.setattr(eda_reporter, "PROCESSED_DIR", tmp_path)
    monkeypatch.setattr(eda_reporter, "PLOTS_DIR", tmp_path / "eda_plots")
    from utils.eda_reporter import generate_report
    out_path = generate_report(verbose=False)
    assert out_path.exists(), f"Report file not created at {out_path}"
    content = out_path.read_text(encoding="utf-8")
    assert "# Analytics Intelligence Platform" in content
    assert "Top 10 Key Metrics" in content


# ── Test 3: EDA report file is created ───────────────────────────────────────

def test_eda_report_file_exists():
    """At least one EDA report file should exist in data/processed/."""
    reports = list(PROCESSED_DIR.glob("eda_report_*.md"))
    assert len(reports) >= 1, (
        f"No eda_report_*.md found in {PROCESSED_DIR}. Run utils/eda_reporter.py first."
    )


def test_eda_report_content():
    """The latest EDA report has expected sections."""
    reports = sorted(PROCESSED_DIR.glob("eda_report_*.md"))
    assert len(reports) >= 1
    content = reports[-1].read_text(encoding="utf-8")
    assert "Top 10 Key Metrics" in content
    assert "Actionable Insights" in content
    assert "Recommended Next Steps" in content


# ── Test 4: Plots saved to correct folder ────────────────────────────────────

def test_eda_plots_directory_exists():
    assert EDA_PLOTS_DIR.exists(), f"EDA plots dir not found: {EDA_PLOTS_DIR}"


def test_eda_plots_png_files_exist():
    pngs = list(EDA_PLOTS_DIR.glob("*.png"))
    assert len(pngs) >= 1, (
        f"No PNG files found in {EDA_PLOTS_DIR}. Run the EDA notebook Section 16 first."
    )


def test_eda_expected_plots_exist():
    """Check that at least some of the expected plots are present."""
    expected = ["channel_share.png", "device_sessions.png",
                "hourly_traffic.png", "daily_sessions.png"]
    existing = {p.name for p in EDA_PLOTS_DIR.glob("*.png")}
    found = [e for e in expected if e in existing]
    assert len(found) >= 2, (
        f"Expected at least 2 of {expected}, found: {sorted(existing)}"
    )
