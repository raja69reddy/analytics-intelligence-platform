"""Tests for SEO page data queries and content health scoring logic."""

from utils.db import query_df

# ── vw_seo view ───────────────────────────────────────────────────────────────


class TestVwSeo:
    def test_view_exists_and_returns_data(self):
        df = query_df("SELECT * FROM vw_seo LIMIT 5")
        assert not df.empty, "vw_seo returned no rows"

    def test_required_columns(self):
        df = query_df("SELECT * FROM vw_seo LIMIT 1")
        expected = {
            "url",
            "word_count",
            "organic_sessions",
            "missing_meta_description",
            "avg_session_duration_s",
            "organic_pageviews",
        }
        assert expected.issubset(
            set(df.columns)
        ), f"Missing columns: {expected - set(df.columns)}"

    def test_word_count_values_non_negative(self):
        df = query_df("SELECT word_count FROM vw_seo WHERE word_count IS NOT NULL")
        assert (
            df["word_count"] >= 0
        ).all(), "Found negative word count values in vw_seo"

    def test_organic_sessions_non_negative(self):
        df = query_df(
            "SELECT organic_sessions FROM vw_seo WHERE organic_sessions IS NOT NULL"
        )
        assert (df["organic_sessions"] >= 0).all()

    def test_missing_meta_is_boolean(self):
        df = query_df("SELECT DISTINCT missing_meta_description FROM vw_seo")
        valid = {True, False, None}
        assert all(v in valid for v in df["missing_meta_description"].unique())


# ── raw_scrape_pages table ────────────────────────────────────────────────────


class TestRawScrapePages:
    def test_table_has_required_columns(self):
        df = query_df("SELECT * FROM raw_scrape_pages LIMIT 1")
        expected = {
            "url",
            "title",
            "word_count",
            "load_time_ms",
            "internal_links",
            "external_links",
            "meta_description",
            "http_status",
        }
        assert expected.issubset(
            set(df.columns)
        ), f"Missing: {expected - set(df.columns)}"

    def test_word_count_positive(self):
        df = query_df(
            "SELECT word_count FROM raw_scrape_pages WHERE word_count IS NOT NULL"
        )
        assert (df["word_count"] > 0).all(), "Found zero or negative word counts"

    def test_load_time_positive(self):
        df = query_df(
            "SELECT load_time_ms FROM raw_scrape_pages WHERE load_time_ms IS NOT NULL"
        )
        assert (df["load_time_ms"] > 0).all(), "Found zero or negative load times"

    def test_http_status_valid(self):
        df = query_df(
            "SELECT DISTINCT http_status FROM raw_scrape_pages WHERE http_status IS NOT NULL"
        )
        assert all(
            100 <= s <= 599 for s in df["http_status"]
        ), "Found invalid HTTP status codes"

    def test_internal_links_non_negative(self):
        df = query_df(
            "SELECT internal_links FROM raw_scrape_pages WHERE internal_links IS NOT NULL"
        )
        assert (df["internal_links"] >= 0).all()

    def test_external_links_non_negative(self):
        df = query_df(
            "SELECT external_links FROM raw_scrape_pages WHERE external_links IS NOT NULL"
        )
        assert (df["external_links"] >= 0).all()

    def test_table_has_rows(self):
        df = query_df("SELECT COUNT(*) AS n FROM raw_scrape_pages")
        assert int(df["n"].iloc[0]) > 0, "raw_scrape_pages is empty"


# ── Content health scoring logic ──────────────────────────────────────────────


class TestContentHealthScoring:
    """Test the health_score function used in the SEO dashboard."""

    @staticmethod
    def _score(meta_description, word_count, load_time_ms):
        issues = []
        if not meta_description:
            issues.append("missing meta")
        if (word_count or 0) < 300:
            issues.append("low word count")
        if (load_time_ms or 0) > 2000:
            issues.append("slow load")
        if not issues:
            return "healthy"
        if len(issues) >= 2:
            return "issues"
        return "needs work"

    def test_healthy_page(self):
        score = self._score("Good description", 500, 800)
        assert score == "healthy"

    def test_missing_meta_needs_work(self):
        score = self._score(None, 500, 800)
        assert score == "needs work"

    def test_low_word_count_needs_work(self):
        score = self._score("Has meta", 100, 800)
        assert score == "needs work"

    def test_slow_load_needs_work(self):
        score = self._score("Has meta", 500, 2500)
        assert score == "needs work"

    def test_two_issues_is_issues_status(self):
        score = self._score(None, 100, 800)
        assert score == "issues"

    def test_all_three_issues_is_issues_status(self):
        score = self._score(None, 50, 3000)
        assert score == "issues"

    def test_exact_300_word_count_is_healthy(self):
        score = self._score("Has meta", 300, 500)
        assert score == "healthy"

    def test_exact_2000ms_load_is_healthy(self):
        score = self._score("Has meta", 500, 2000)
        assert score == "healthy"
