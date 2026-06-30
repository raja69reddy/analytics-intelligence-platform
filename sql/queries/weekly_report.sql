-- weekly_report.sql: weekly summary with WoW growth, top pages, channels, and error rate.

-- Query 1: Weekly sessions summary
SELECT
    DATE_TRUNC('week', session_date)::date          AS week_start,
    SUM(sessions)                                   AS total_sessions,
    SUM(new_users)                                  AS new_users,
    SUM(pageviews)                                  AS total_pageviews,
    ROUND(AVG(session_duration_s)::numeric, 2)      AS avg_session_duration,
    ROUND(
        100.0 * SUM(CASE WHEN bounce THEN sessions ELSE 0 END)
        / NULLIF(SUM(sessions), 0), 2
    )                                               AS bounce_rate_pct
FROM raw_ga4_sessions
GROUP BY DATE_TRUNC('week', session_date)
ORDER BY week_start;

-- Query 2: Week over week session growth rate
WITH weekly AS (
    SELECT
        DATE_TRUNC('week', session_date)::date      AS week_start,
        SUM(sessions)                               AS total_sessions
    FROM raw_ga4_sessions
    GROUP BY DATE_TRUNC('week', session_date)
)
SELECT
    week_start,
    total_sessions,
    LAG(total_sessions) OVER (ORDER BY week_start)  AS prev_week_sessions,
    ROUND(
        100.0 * (total_sessions - LAG(total_sessions) OVER (ORDER BY week_start))
        / NULLIF(LAG(total_sessions) OVER (ORDER BY week_start), 0), 2
    )                                               AS wow_growth_pct
FROM weekly
ORDER BY week_start;

-- Query 3: Top 5 pages this week by request count
SELECT
    url,
    total_requests,
    unique_visitors,
    avg_response_time_ms,
    error_rate_pct
FROM vw_top_pages
ORDER BY total_requests DESC
LIMIT 5;

-- Query 4: Top 3 channels this week by sessions
SELECT
    channel_grouping,
    total_sessions,
    channel_share_pct,
    bounce_rate_pct,
    avg_session_duration
FROM vw_channel_performance
ORDER BY total_sessions DESC
LIMIT 3;

-- Query 5: Error rate this week
SELECT
    SUM(total_requests)                                             AS total_requests,
    SUM(total_errors)                                               AS total_errors,
    ROUND(100.0 * SUM(total_errors) / NULLIF(SUM(total_requests), 0), 2) AS overall_error_rate_pct
FROM vw_error_pages;
