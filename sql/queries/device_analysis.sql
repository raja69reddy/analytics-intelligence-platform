-- Device Analysis Queries
-- All queries use raw_ga4_sessions.

-- 1. Sessions by device type over time (weekly)
SELECT
    DATE_TRUNC('week', session_date)::DATE AS week_start,
    device_category,
    SUM(sessions)  AS sessions,
    SUM(new_users) AS new_users,
    ROUND(SUM(sessions)::NUMERIC / SUM(SUM(sessions)) OVER (PARTITION BY DATE_TRUNC('week', session_date)) * 100, 2) AS device_share_pct
FROM raw_ga4_sessions
GROUP BY week_start, device_category
ORDER BY week_start, sessions DESC;


-- 2. Conversion rate by device type
SELECT
    device_category,
    SUM(sessions)    AS total_sessions,
    SUM(conversions) AS total_conversions,
    ROUND(SUM(conversions)::NUMERIC / NULLIF(SUM(sessions), 0) * 100, 4) AS cvr_pct,
    SUM(revenue)     AS total_revenue,
    ROUND(SUM(revenue) / NULLIF(SUM(sessions), 0), 4)                    AS revenue_per_session
FROM raw_ga4_sessions
GROUP BY device_category
ORDER BY cvr_pct DESC;


-- 3. Bounce rate by device type
SELECT
    device_category,
    SUM(sessions)  AS total_sessions,
    SUM(bounce::INT)  AS bounces,
    ROUND(SUM(bounce::INT)::NUMERIC / NULLIF(SUM(sessions), 0) * 100, 2) AS bounce_rate_pct,
    ROUND(AVG(session_duration_s), 1) AS avg_duration_s
FROM raw_ga4_sessions
GROUP BY device_category
ORDER BY bounce_rate_pct ASC;


-- 4. Avg session duration by device type
SELECT
    device_category,
    SUM(sessions) AS total_sessions,
    ROUND(AVG(session_duration_s), 1) AS avg_duration_s,
    ROUND(AVG(pageviews), 2)          AS avg_pageviews,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY session_duration_s) AS median_duration_s
FROM raw_ga4_sessions
GROUP BY device_category
ORDER BY avg_duration_s DESC;


-- 5. Page load time by device type (from raw_scrape_pages by device hint in URL)
-- As raw_scrape_pages has no device column, use avg load time overall as proxy
SELECT
    ga.device_category,
    SUM(ga.sessions)  AS ga_sessions,
    ROUND(AVG(ga.session_duration_s), 1) AS avg_session_s,
    sp.avg_load_ms
FROM raw_ga4_sessions ga
CROSS JOIN (
    SELECT ROUND(AVG(load_time_ms), 0) AS avg_load_ms
    FROM raw_scrape_pages WHERE http_status = 200
) sp
GROUP BY ga.device_category, sp.avg_load_ms
ORDER BY ga_sessions DESC;


-- 6. Revenue by device type
SELECT
    device_category,
    SUM(sessions)    AS total_sessions,
    SUM(revenue)     AS total_revenue,
    ROUND(SUM(revenue) / NULLIF(SUM(sessions), 0), 4) AS revenue_per_session,
    ROUND(SUM(revenue) / NULLIF(SUM(conversions), 0), 4) AS avg_order_value,
    ROUND(SUM(revenue)::NUMERIC / NULLIF(SUM(SUM(revenue)) OVER (), 0) * 100, 2) AS revenue_share_pct
FROM raw_ga4_sessions
GROUP BY device_category
ORDER BY total_revenue DESC;
