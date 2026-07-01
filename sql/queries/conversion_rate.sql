-- ============================================================
-- Conversion Rate Analysis
-- Source: raw_ga4_sessions
-- ============================================================


-- 1. Overall conversion rate by date
SELECT
    session_date,
    SUM(sessions)                                                           AS total_sessions,
    SUM(conversions)                                                        AS total_conversions,
    ROUND(SUM(conversions)::NUMERIC / NULLIF(SUM(sessions), 0) * 100, 2)   AS cvr_pct
FROM raw_ga4_sessions
GROUP BY session_date
ORDER BY session_date;


-- 2. Conversion rate by channel
SELECT
    channel_grouping,
    SUM(sessions)                                                           AS total_sessions,
    SUM(conversions)                                                        AS total_conversions,
    ROUND(SUM(conversions)::NUMERIC / NULLIF(SUM(sessions), 0) * 100, 2)   AS cvr_pct,
    SUM(revenue)                                                            AS total_revenue
FROM raw_ga4_sessions
GROUP BY channel_grouping
ORDER BY cvr_pct DESC;


-- 3. Conversion rate by device type
SELECT
    device_category,
    SUM(sessions)                                                           AS total_sessions,
    SUM(conversions)                                                        AS total_conversions,
    ROUND(SUM(conversions)::NUMERIC / NULLIF(SUM(sessions), 0) * 100, 2)   AS cvr_pct
FROM raw_ga4_sessions
GROUP BY device_category
ORDER BY cvr_pct DESC;


-- 4. Conversion rate by landing page (top 20 pages)
SELECT
    landing_page,
    SUM(sessions)                                                           AS total_sessions,
    SUM(conversions)                                                        AS total_conversions,
    ROUND(SUM(conversions)::NUMERIC / NULLIF(SUM(sessions), 0) * 100, 2)   AS cvr_pct,
    SUM(revenue)                                                            AS total_revenue
FROM raw_ga4_sessions
WHERE landing_page IS NOT NULL
GROUP BY landing_page
ORDER BY total_sessions DESC
LIMIT 20;


-- 5. Week-over-week conversion rate change
WITH weekly AS (
    SELECT
        DATE_TRUNC('week', session_date)::DATE                             AS week_start,
        SUM(sessions)                                                       AS sessions,
        SUM(conversions)                                                    AS conversions,
        ROUND(SUM(conversions)::NUMERIC / NULLIF(SUM(sessions), 0) * 100, 2) AS cvr_pct
    FROM raw_ga4_sessions
    GROUP BY 1
)
SELECT
    week_start,
    sessions,
    conversions,
    cvr_pct,
    LAG(cvr_pct) OVER (ORDER BY week_start)                                AS prev_week_cvr,
    ROUND(cvr_pct - LAG(cvr_pct) OVER (ORDER BY week_start), 2)           AS wow_change_ppt
FROM weekly
ORDER BY week_start;


-- 6. Month-over-month conversion rate change
WITH monthly AS (
    SELECT
        DATE_TRUNC('month', session_date)::DATE                            AS month_start,
        SUM(sessions)                                                       AS sessions,
        SUM(conversions)                                                    AS conversions,
        ROUND(SUM(conversions)::NUMERIC / NULLIF(SUM(sessions), 0) * 100, 2) AS cvr_pct
    FROM raw_ga4_sessions
    GROUP BY 1
)
SELECT
    month_start,
    sessions,
    conversions,
    cvr_pct,
    LAG(cvr_pct) OVER (ORDER BY month_start)                               AS prev_month_cvr,
    ROUND(cvr_pct - LAG(cvr_pct) OVER (ORDER BY month_start), 2)          AS mom_change_ppt
FROM monthly
ORDER BY month_start;
