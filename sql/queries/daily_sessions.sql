-- daily_sessions.sql: daily session counts and KPIs for a given date range (:start_date, :end_date).

SELECT
    d.full_date,
    d.day_name,
    d.week,
    d.is_weekend,
    COUNT(*)                                                AS sessions,
    SUM(CASE WHEN s.is_new_user THEN 1 ELSE 0 END)         AS new_users,
    COUNT(*) - SUM(CASE WHEN s.is_new_user THEN 1 ELSE 0 END) AS returning_users,
    SUM(s.pageviews)                                        AS pageviews,
    ROUND(AVG(s.pageviews), 2)                              AS avg_pages_per_session,
    SUM(CASE WHEN s.bounced THEN 1 ELSE 0 END)              AS bounces,
    ROUND(
        100.0 * SUM(CASE WHEN s.bounced THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2
    )                                                       AS bounce_rate_pct,
    ROUND(AVG(s.session_duration_s), 2)                     AS avg_session_duration_s,
    SUM(s.conversions)                                      AS conversions,
    SUM(s.revenue)                                          AS revenue
FROM fct_sessions s
JOIN dim_dates d ON s.date_id = d.date_id
WHERE d.full_date BETWEEN :start_date AND :end_date
GROUP BY d.full_date, d.day_name, d.week, d.is_weekend
ORDER BY d.full_date;
