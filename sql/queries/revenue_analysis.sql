-- ============================================================
-- Revenue Analysis
-- Source: raw_ga4_sessions
-- ============================================================


-- 1. Total revenue by date
SELECT
    session_date,
    SUM(revenue)                                                            AS total_revenue,
    SUM(conversions)                                                        AS conversions,
    ROUND(SUM(revenue) / NULLIF(SUM(conversions), 0), 2)                   AS avg_order_value
FROM raw_ga4_sessions
GROUP BY session_date
ORDER BY session_date;


-- 2. Revenue by channel
SELECT
    channel_grouping,
    SUM(sessions)                                                           AS total_sessions,
    SUM(conversions)                                                        AS conversions,
    SUM(revenue)                                                            AS total_revenue,
    ROUND(SUM(revenue) / NULLIF(SUM(sessions), 0), 4)                      AS revenue_per_session,
    ROUND(SUM(revenue) / NULLIF(SUM(conversions), 0), 2)                   AS avg_order_value
FROM raw_ga4_sessions
GROUP BY channel_grouping
ORDER BY total_revenue DESC;


-- 3. Revenue by device type
SELECT
    device_category,
    SUM(sessions)                                                           AS total_sessions,
    SUM(revenue)                                                            AS total_revenue,
    ROUND(SUM(revenue) / NULLIF(SUM(sessions), 0), 4)                      AS revenue_per_session,
    ROUND(SUM(revenue) / NULLIF(SUM(conversions), 0), 2)                   AS avg_order_value
FROM raw_ga4_sessions
GROUP BY device_category
ORDER BY total_revenue DESC;


-- 4. Average order value by channel
SELECT
    channel_grouping,
    COUNT(CASE WHEN conversions > 0 THEN 1 END)                            AS converting_sessions,
    ROUND(SUM(revenue) / NULLIF(SUM(conversions), 0), 2)                   AS avg_order_value,
    MIN(CASE WHEN revenue > 0 THEN revenue END)                            AS min_order_value,
    MAX(revenue)                                                            AS max_order_value
FROM raw_ga4_sessions
GROUP BY channel_grouping
ORDER BY avg_order_value DESC NULLS LAST;


-- 5. Revenue per session by channel
SELECT
    channel_grouping,
    SUM(sessions)                                                           AS total_sessions,
    SUM(revenue)                                                            AS total_revenue,
    ROUND(SUM(revenue) / NULLIF(SUM(sessions), 0), 4)                      AS revenue_per_session
FROM raw_ga4_sessions
GROUP BY channel_grouping
ORDER BY revenue_per_session DESC;


-- 6. Top 10 landing pages by revenue generated
SELECT
    landing_page                                                            AS page,
    SUM(sessions)                                                           AS total_sessions,
    SUM(conversions)                                                        AS conversions,
    SUM(revenue)                                                            AS total_revenue,
    ROUND(SUM(revenue) / NULLIF(SUM(sessions), 0), 4)                      AS revenue_per_session
FROM raw_ga4_sessions
WHERE landing_page IS NOT NULL
GROUP BY landing_page
ORDER BY total_revenue DESC
LIMIT 10;
