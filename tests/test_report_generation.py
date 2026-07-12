"""Unit tests for ai/report_generation/generator.py and formatter.py."""

import os
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from ai.report_generation.formatter import (
    format_as_html,
    format_as_markdown,
    save_report,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────

SAMPLE_REPORT = {
    "traffic": "Traffic was strong this month with 10,000 sessions across 6 channels.",
    "behavior": "Users spent an average of 3 minutes per session with 65% scroll depth.",
    "conversions": "Conversion rate reached 3.2% generating $12,450 in revenue.",
    "seo": "Organic traffic grew 15% with 45 pages indexed and crawled successfully.",
    "executive_summary": "Platform performance is healthy. Top priority: improve CVR by 0.5%.",
    "generated_at": "2026-06-30 12:00:00",
}


# ── ReportGenerator initialization ───────────────────────────────────────────


def test_report_generator_initializes():
    from ai.report_generation.generator import ReportGenerator

    gen = ReportGenerator()
    assert gen is not None
    assert gen.model == "gpt-3.5-turbo"


def test_report_generator_accepts_custom_model():
    from ai.report_generation.generator import ReportGenerator

    gen = ReportGenerator(model="gpt-4")
    assert gen.model == "gpt-4"


def test_report_generator_raises_without_api_key():
    from ai.report_generation.generator import ReportGenerator

    gen = ReportGenerator()
    with patch.dict(os.environ, {}, clear=True):
        # Remove OPENAI_API_KEY if set
        os.environ.pop("OPENAI_API_KEY", None)
        with pytest.raises((EnvironmentError, ImportError)):
            _ = gen.client


# ── generate_traffic_report (mocked API) ─────────────────────────────────────


def test_generate_traffic_report_returns_string():
    from ai.report_generation.generator import ReportGenerator

    gen = ReportGenerator()
    gen._call_api = MagicMock(return_value="Traffic is up 12% month over month.")
    df = pd.DataFrame({"session_date": ["2026-06-01"], "total_sessions": [500]})
    result = gen.generate_traffic_report(df)
    assert isinstance(result, str)
    assert len(result) > 0


def test_generate_behavior_report_returns_string():
    from ai.report_generation.generator import ReportGenerator

    gen = ReportGenerator()
    gen._call_api = MagicMock(return_value="Users engage deeply with product pages.")
    df = pd.DataFrame({"url": ["/products"], "total_requests": [1200]})
    result = gen.generate_behavior_report(df)
    assert isinstance(result, str)


def test_generate_conversion_report_returns_string():
    from ai.report_generation.generator import ReportGenerator

    gen = ReportGenerator()
    gen._call_api = MagicMock(return_value="CVR is 3.5%, above the 3% benchmark.")
    df = pd.DataFrame(
        {"channel_grouping": ["Email"], "cvr_pct": [3.5], "revenue": [5000]}
    )
    result = gen.generate_conversion_report(df)
    assert isinstance(result, str)


def test_generate_seo_report_returns_string():
    from ai.report_generation.generator import ReportGenerator

    gen = ReportGenerator()
    gen._call_api = MagicMock(return_value="Organic search is growing steadily.")
    df = pd.DataFrame({"url": ["/blog"], "word_count": [800]})
    result = gen.generate_seo_report(df)
    assert isinstance(result, str)


# ── format_as_markdown ────────────────────────────────────────────────────────


def test_format_as_markdown_contains_title():
    md = format_as_markdown(SAMPLE_REPORT)
    assert "# Analytics Intelligence Report" in md


def test_format_as_markdown_contains_all_sections():
    md = format_as_markdown(SAMPLE_REPORT)
    assert "## Traffic & Sessions" in md
    assert "## User Behavior" in md
    assert "## Conversions" in md
    assert "## SEO & Content" in md


def test_format_as_markdown_contains_executive_summary():
    md = format_as_markdown(SAMPLE_REPORT)
    assert "## Executive Summary" in md
    assert SAMPLE_REPORT["executive_summary"] in md


def test_format_as_markdown_contains_generated_at():
    md = format_as_markdown(SAMPLE_REPORT)
    assert "2026-06-30 12:00:00" in md


def test_format_as_markdown_returns_string():
    result = format_as_markdown(SAMPLE_REPORT)
    assert isinstance(result, str)
    assert len(result) > 100


# ── format_as_html ────────────────────────────────────────────────────────────


def test_format_as_html_is_valid_html():
    html = format_as_html(SAMPLE_REPORT)
    assert "<!DOCTYPE html>" in html
    assert "<html>" in html
    assert "</html>" in html


def test_format_as_html_contains_sections():
    html = format_as_html(SAMPLE_REPORT)
    assert "Traffic" in html
    assert "Conversions" in html


# ── save_report ────────────────────────────────────────────────────────────────


def test_save_report_creates_file(tmp_path, monkeypatch):
    import ai.report_generation.formatter as fmt_module

    monkeypatch.setattr(fmt_module, "REPORTS_DIR", tmp_path)
    path = save_report(SAMPLE_REPORT, filename="test_report.md")
    assert path.exists()
    assert path.name == "test_report.md"


def test_save_report_content_is_markdown(tmp_path, monkeypatch):
    import ai.report_generation.formatter as fmt_module

    monkeypatch.setattr(fmt_module, "REPORTS_DIR", tmp_path)
    path = save_report(SAMPLE_REPORT, filename="test_report2.md")
    content = path.read_text(encoding="utf-8")
    assert "# Analytics Intelligence Report" in content
    assert "Traffic" in content


def test_save_report_auto_filename(tmp_path, monkeypatch):
    import ai.report_generation.formatter as fmt_module

    monkeypatch.setattr(fmt_module, "REPORTS_DIR", tmp_path)
    path = save_report(SAMPLE_REPORT)
    assert path.name.startswith("report_")
    assert path.name.endswith(".md")
    assert path.exists()
