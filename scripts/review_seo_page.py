"""Day 51 — SEO page end-to-end review."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.db import query_df


def run():
    checks = [
        ("vw_seo", "SELECT * FROM vw_seo LIMIT 10"),
        ("raw_scrape_pages", "SELECT * FROM raw_scrape_pages WHERE http_status=200 LIMIT 5"),
        (
            "Word count scatter",
            """SELECT DISTINCT ON (sp.url)
                   sp.url, sp.word_count, sp.load_time_ms,
                   COALESCE(v.organic_sessions, 0) AS organic_sessions,
                   COALESCE(v.organic_pageviews, 0) AS pageviews
               FROM raw_scrape_pages sp LEFT JOIN vw_seo v ON v.url = sp.url
               WHERE sp.http_status = 200 AND sp.word_count IS NOT NULL AND sp.word_count > 0
               ORDER BY sp.url, sp.scraped_at DESC""",
        ),
        (
            "Content health",
            """SELECT DISTINCT ON (url) url, title, meta_description, word_count,
                   load_time_ms, http_status, internal_links
               FROM raw_scrape_pages WHERE http_status = 200
               ORDER BY url, scraped_at DESC""",
        ),
        (
            "Load time distribution",
            "SELECT DISTINCT ON (url) url, load_time_ms FROM raw_scrape_pages "
            "WHERE http_status = 200 ORDER BY url, scraped_at DESC",
        ),
        (
            "Links analysis",
            """SELECT DISTINCT ON (sp.url)
                   sp.url, sp.internal_links, sp.external_links,
                   COALESCE(v.organic_sessions, 0) AS organic_sessions
               FROM raw_scrape_pages sp LEFT JOIN vw_seo v ON v.url = sp.url
               WHERE sp.http_status = 200 ORDER BY sp.url, sp.scraped_at DESC""",
        ),
        (
            "Content score data",
            """SELECT DISTINCT ON (url) url, word_count, load_time_ms,
                   meta_description, internal_links
               FROM raw_scrape_pages WHERE http_status = 200
               ORDER BY url, scraped_at DESC""",
        ),
        (
            "Keyword analysis",
            """SELECT DISTINCT ON (url) url, title, meta_description, word_count
               FROM raw_scrape_pages WHERE http_status = 200
               ORDER BY url, scraped_at DESC""",
        ),
        (
            "Content freshness",
            """SELECT DISTINCT ON (url) url, title, word_count, load_time_ms, scraped_at,
                   EXTRACT(EPOCH FROM (NOW() - scraped_at)) / 86400.0 AS days_since_scraped
               FROM raw_scrape_pages WHERE http_status = 200
               ORDER BY url, scraped_at DESC""",
        ),
        (
            "Content gap analysis",
            """SELECT DISTINCT ON (sp.url) sp.url, sp.word_count, sp.load_time_ms,
                   COALESCE(v.organic_sessions, 0) AS organic_sessions
               FROM raw_scrape_pages sp LEFT JOIN vw_seo v ON v.url = sp.url
               WHERE sp.http_status=200 AND sp.word_count > 0
               ORDER BY sp.url, sp.scraped_at DESC""",
        ),
        (
            "SEO recommendations data",
            """SELECT DISTINCT ON (sp.url) sp.url, sp.title, sp.meta_description,
                   sp.word_count, sp.load_time_ms, sp.internal_links,
                   COALESCE(v.organic_sessions, 0) AS organic_sessions
               FROM raw_scrape_pages sp LEFT JOIN vw_seo v ON v.url = sp.url
               WHERE sp.http_status=200 ORDER BY sp.url, sp.scraped_at DESC""",
        ),
        (
            "Content ROI",
            """SELECT landing_page AS url, SUM(sessions) AS total_sessions,
                   ROUND(SUM(revenue)::NUMERIC / NULLIF(SUM(sessions), 0), 4) AS revenue_per_visit
               FROM raw_ga4_sessions WHERE landing_page IS NOT NULL AND sessions > 0
               GROUP BY landing_page HAVING SUM(sessions) >= 5""",
        ),
        (
            "SEO score trend",
            """SELECT DATE(scraped_at) AS scrape_date,
                   ROUND(AVG(word_count)) AS avg_word_count,
                   ROUND(AVG(internal_links), 2) AS avg_internal_links,
                   ROUND(AVG(load_time_ms)) AS avg_load_time_ms
               FROM raw_scrape_pages WHERE http_status = 200
               GROUP BY DATE(scraped_at) ORDER BY scrape_date""",
        ),
    ]

    all_ok = True
    print("SEO page end-to-end review")
    print("=" * 45)
    for name, sql in checks:
        try:
            df = query_df(sql)
            print(f"  PASS  {name} ({len(df)} rows)")
        except Exception as exc:
            print(f"  FAIL  {name} -> {exc}")
            all_ok = False

    print()
    if all_ok:
        print("SEO page review: PASSED")
    else:
        print("SEO page review: FAILED")
        sys.exit(1)


if __name__ == "__main__":
    run()
