-- dashboard_summary.sql
-- Single query returning all home-page KPIs, top performers, and date-range metadata.
-- Run against the web_analytics PostgreSQL database.
-- Parameterised with :start_date / :end_date (YYYY-MM-DD).  Pass NULLs for all-time.

WITH date_range AS (
    SELECT
        MIN(session_date)::date  AS data_start,
        MAX(session_date)::date  AS data_end
    FROM raw_ga4_sessions
),

session_kpis AS (
    SELECT
        COALESCE(SUM(sessions), 0)                                        AS total_sessions,
        COALESCE(SUM(new_users), 0)                                       AS total_users,
        COALESCE(SUM(pageviews), 0)                                       AS total_pageviews,
        ROUND(
            100.0 * COALESCE(SUM(CASE WHEN bounce THEN sessions ELSE 0 END), 0)::numeric
            / NULLIF(SUM(sessions), 0),
            2
        )                                                                 AS avg_bounce_rate_pct
    FROM raw_ga4_sessions
    WHERE (:start_date IS NULL OR session_date >= :start_date)
      AND (:end_date   IS NULL OR session_date <= :end_date)
),

conversion_kpis AS (
    SELECT
        ROUND(
            100.0 * SUM(goal_completions)::numeric / NULLIF(SUM(sessions), 0),
            2
        )                                                                 AS overall_cvr_pct,
        COALESCE(SUM(goal_completions), 0)                                AS total_conversions
    FROM vw_conversions
    WHERE (:start_date IS NULL OR session_date >= :start_date)
      AND (:end_date   IS NULL OR session_date <= :end_date)
),

top_channel AS (
    SELECT channel_grouping AS top_channel
    FROM raw_ga4_sessions
    WHERE (:start_date IS NULL OR session_date >= :start_date)
      AND (:end_date   IS NULL OR session_date <= :end_date)
    GROUP BY channel_grouping
    ORDER BY SUM(sessions) DESC
    LIMIT 1
),

top_page AS (
    SELECT url AS top_page
    FROM raw_server_logs
    WHERE (:start_date IS NULL OR DATE(log_time) >= :start_date)
      AND (:end_date   IS NULL OR DATE(log_time) <= :end_date)
    GROUP BY url
    ORDER BY COUNT(*) DESC
    LIMIT 1
),

top_device AS (
    SELECT device_category AS top_device
    FROM raw_ga4_sessions
    WHERE (:start_date IS NULL OR session_date >= :start_date)
      AND (:end_date   IS NULL OR session_date <= :end_date)
    GROUP BY device_category
    ORDER BY SUM(sessions) DESC
    LIMIT 1
)

SELECT
    -- Volume
    s.total_sessions,
    s.total_users,
    s.total_pageviews,
    -- Rates
    s.avg_bounce_rate_pct,
    c.overall_cvr_pct,
    c.total_conversions,
    -- Top performers
    tc.top_channel,
    tp.top_page,
    td.top_device,
    -- Date range of available data
    dr.data_start,
    dr.data_end
FROM session_kpis      s
CROSS JOIN conversion_kpis  c
CROSS JOIN top_channel       tc
CROSS JOIN top_page          tp
CROSS JOIN top_device        td
CROSS JOIN date_range        dr;
