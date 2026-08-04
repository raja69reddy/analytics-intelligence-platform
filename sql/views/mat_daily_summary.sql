-- mat_daily_summary: pre-aggregated daily KPIs for the dashboard home page.
-- Refresh with: REFRESH MATERIALIZED VIEW mat_daily_summary;

DROP MATERIALIZED VIEW IF EXISTS mat_daily_summary;
CREATE MATERIALIZED VIEW mat_daily_summary AS
WITH daily_ga4 AS (
    SELECT
        session_date                          AS report_date,
        SUM(sessions)                         AS total_sessions,
        SUM(new_users)                        AS total_new_users,
        SUM(pageviews)                        AS total_pageviews,
        SUM(conversions)                      AS total_conversions,
        SUM(revenue)                          AS total_revenue,
        ROUND(
            100.0 * SUM(CASE WHEN bounce THEN sessions ELSE 0 END)
            / NULLIF(SUM(sessions), 0), 2
        )                                     AS avg_bounce_rate_pct,
        ROUND(AVG(session_duration_s)::numeric, 1) AS avg_session_duration_s
    FROM raw_ga4_sessions
    GROUP BY session_date
),
daily_events AS (
    SELECT
        DATE(event_time)                      AS report_date,
        COUNT(*)                              AS total_events,
        COUNT(DISTINCT session_id)            AS active_sessions,
        ROUND(AVG(scroll_depth_pct)::numeric, 1) AS avg_scroll_depth_pct
    FROM raw_clickstream_events
    WHERE event_time IS NOT NULL
    GROUP BY DATE(event_time)
),
daily_logs AS (
    SELECT
        DATE(log_time)                        AS report_date,
        COUNT(*)                              AS total_requests,
        COUNT(CASE WHEN status_code >= 400 THEN 1 END) AS error_requests,
        ROUND(
            100.0 * COUNT(CASE WHEN status_code >= 400 THEN 1 END)
            / NULLIF(COUNT(*), 0), 2
        )                                     AS error_rate_pct,
        ROUND(AVG(response_time_ms)::numeric, 1) AS avg_response_ms
    FROM raw_server_logs
    WHERE log_time IS NOT NULL
    GROUP BY DATE(log_time)
)
SELECT
    g.report_date,
    COALESCE(d.year,  EXTRACT(YEAR  FROM g.report_date)::int) AS year,
    COALESCE(d.month, EXTRACT(MONTH FROM g.report_date)::int) AS month,
    COALESCE(d.week,  EXTRACT(WEEK  FROM g.report_date)::int) AS week,
    COALESCE(d.day_name, TO_CHAR(g.report_date, 'Day'))       AS day_name,
    COALESCE(d.is_weekend, EXTRACT(DOW FROM g.report_date) IN (0,6)) AS is_weekend,
    -- GA4 metrics
    g.total_sessions,
    g.total_new_users,
    g.total_pageviews,
    g.total_conversions,
    g.total_revenue,
    g.avg_bounce_rate_pct,
    g.avg_session_duration_s,
    -- event metrics
    COALESCE(e.total_events,       0) AS total_events,
    COALESCE(e.active_sessions,    0) AS active_sessions,
    COALESCE(e.avg_scroll_depth_pct, 0) AS avg_scroll_depth_pct,
    -- server log metrics
    COALESCE(l.total_requests,     0) AS total_requests,
    COALESCE(l.error_requests,     0) AS error_requests,
    COALESCE(l.error_rate_pct,     0) AS error_rate_pct,
    COALESCE(l.avg_response_ms,    0) AS avg_response_ms,
    -- derived KPIs
    ROUND(
        COALESCE(g.total_conversions, 0) * 100.0
        / NULLIF(g.total_sessions, 0), 3
    )                                  AS conversion_rate_pct,
    ROUND(
        COALESCE(g.total_revenue, 0)
        / NULLIF(g.total_sessions, 0), 2
    )                                  AS revenue_per_session
FROM daily_ga4 g
LEFT JOIN dim_dates       d ON d.full_date = g.report_date
LEFT JOIN daily_events    e ON e.report_date = g.report_date
LEFT JOIN daily_logs      l ON l.report_date = g.report_date
ORDER BY g.report_date;
