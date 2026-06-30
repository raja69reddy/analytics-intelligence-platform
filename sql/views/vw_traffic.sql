-- vw_traffic: sessions, pageviews, bounce rate, and revenue by date and channel.
CREATE OR REPLACE VIEW vw_traffic AS
SELECT
    d.full_date,
    d.year,
    d.month,
    d.week,
    d.day_name,
    s.channel_grouping,
    s.source,
    s.medium,
    s.country,
    s.device_category,
    COUNT(*)                                    AS sessions,
    SUM(CASE WHEN s.is_new_user THEN 1 ELSE 0 END) AS new_users,
    SUM(s.pageviews)                            AS pageviews,
    SUM(CASE WHEN s.bounced THEN 1 ELSE 0 END)  AS bounces,
    ROUND(
        100.0 * SUM(CASE WHEN s.bounced THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2
    )                                           AS bounce_rate_pct,
    ROUND(AVG(s.session_duration_s), 2)         AS avg_session_duration_s,
    SUM(s.conversions)                          AS conversions,
    SUM(s.revenue)                              AS revenue
FROM fct_sessions s
JOIN dim_dates d ON s.date_id = d.date_id
GROUP BY 1,2,3,4,5,6,7,8,9,10;
