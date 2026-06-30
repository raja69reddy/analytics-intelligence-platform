-- traffic_summary.sql: 4 reusable traffic analysis queries.

-- Query 1: This month vs last month sessions/pageviews/bounce rate
SELECT
    TO_CHAR(DATE_TRUNC('month', session_date), 'YYYY-MM') AS month,
    SUM(sessions)                                          AS total_sessions,
    SUM(pageviews)                                         AS total_pageviews,
    ROUND(
        100.0 * SUM(CASE WHEN bounce THEN sessions ELSE 0 END)
        / NULLIF(SUM(sessions), 0), 2
    )                                                      AS bounce_rate_pct,
    ROUND(AVG(session_duration_s)::numeric, 2)             AS avg_session_duration
FROM raw_ga4_sessions
WHERE session_date >= DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '1 month'
GROUP BY DATE_TRUNC('month', session_date)
ORDER BY month;

-- Query 2: Top 5 channels by sessions (all time)
SELECT
    channel_grouping,
    SUM(sessions)    AS total_sessions,
    SUM(new_users)   AS total_new_users,
    SUM(pageviews)   AS total_pageviews,
    ROUND(AVG(session_duration_s)::numeric, 2) AS avg_duration
FROM raw_ga4_sessions
GROUP BY channel_grouping
ORDER BY total_sessions DESC
LIMIT 5;

-- Query 3: Last 30 days daily sessions
SELECT
    session_date,
    SUM(sessions)  AS total_sessions,
    SUM(pageviews) AS total_pageviews
FROM raw_ga4_sessions
WHERE session_date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY session_date
ORDER BY session_date;

-- Query 4: New vs returning breakdown (all time)
SELECT
    SUM(sessions)                                                AS total_sessions,
    SUM(new_users)                                               AS new_user_sessions,
    SUM(sessions) - SUM(new_users)                               AS returning_user_sessions,
    ROUND(100.0 * SUM(new_users) / NULLIF(SUM(sessions), 0), 2) AS new_pct,
    ROUND(
        100.0 * (SUM(sessions) - SUM(new_users)) / NULLIF(SUM(sessions), 0), 2
    )                                                            AS returning_pct
FROM raw_ga4_sessions;
