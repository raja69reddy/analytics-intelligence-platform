-- vw_traffic: sessions by date, channel, source, medium from GA4.
-- LEFT JOINs dim_dates for calendar attributes with EXTRACT fallback
-- for dates outside dim_dates coverage (e.g. 2026+).
DROP VIEW IF EXISTS vw_traffic CASCADE;
CREATE OR REPLACE VIEW vw_traffic AS
SELECT
    g.session_date,
    COALESCE(d.year,        EXTRACT(YEAR  FROM g.session_date)::int)    AS year,
    COALESCE(d.month,       EXTRACT(MONTH FROM g.session_date)::int)    AS month,
    COALESCE(d.month_name,  TO_CHAR(g.session_date, 'Month'))           AS month_name,
    COALESCE(d.week,        EXTRACT(WEEK  FROM g.session_date)::int)    AS week,
    COALESCE(d.day_of_week, EXTRACT(DOW   FROM g.session_date)::int)    AS day_of_week,
    COALESCE(d.day_name,    TO_CHAR(g.session_date, 'Day'))             AS day_name,
    COALESCE(d.is_weekend,  EXTRACT(DOW FROM g.session_date) IN (0, 6)) AS is_weekend,
    g.channel_grouping,
    g.source,
    g.medium,
    SUM(g.sessions)                                              AS total_sessions,
    SUM(g.sessions)                                              AS total_users,
    SUM(g.new_users)                                             AS new_users,
    SUM(g.pageviews)                                             AS total_pageviews,
    ROUND(
        100.0 * SUM(CASE WHEN g.bounce THEN g.sessions ELSE 0 END)
        / NULLIF(SUM(g.sessions), 0), 2
    )                                                            AS avg_bounce_rate,
    ROUND(AVG(g.session_duration_s)::numeric, 2)                AS avg_session_duration
FROM raw_ga4_sessions g
LEFT JOIN dim_dates d ON d.full_date = g.session_date
GROUP BY
    g.session_date,
    d.year, d.month, d.month_name, d.week, d.day_of_week, d.day_name, d.is_weekend,
    g.channel_grouping, g.source, g.medium
ORDER BY g.session_date, g.channel_grouping;
