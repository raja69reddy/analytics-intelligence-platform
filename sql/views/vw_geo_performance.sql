-- vw_geo_performance: top 10 countries by sessions with bounce rate and share pct.
CREATE OR REPLACE VIEW vw_geo_performance AS
WITH country_totals AS (
    SELECT
        country,
        SUM(sessions)                                                AS total_sessions,
        SUM(new_users)                                               AS total_new_users,
        SUM(pageviews)                                               AS total_pageviews,
        ROUND(AVG(session_duration_s)::numeric, 2)                   AS avg_session_duration,
        ROUND(
            100.0 * SUM(CASE WHEN bounce THEN sessions ELSE 0 END)
            / NULLIF(SUM(sessions), 0), 2
        )                                                            AS bounce_rate_pct
    FROM raw_ga4_sessions
    WHERE country IS NOT NULL
    GROUP BY country
),
grand_total AS (
    SELECT SUM(total_sessions) AS grand_sessions FROM country_totals
)
SELECT
    c.country,
    c.total_sessions,
    c.total_new_users,
    c.total_pageviews,
    c.avg_session_duration,
    c.bounce_rate_pct,
    ROUND(100.0 * c.total_sessions / NULLIF(g.grand_sessions, 0), 2) AS country_share_pct
FROM country_totals c
CROSS JOIN grand_total g
ORDER BY c.total_sessions DESC
LIMIT 10;
