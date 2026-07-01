-- ============================================================
-- Funnel Analysis
-- Source: raw_ga4_sessions, raw_clickstream_events
-- Stages: Landing → Engaged → Multi-page → Converted → Revenue
-- ============================================================


-- 1. Users at each funnel stage
SELECT
    'Landing'    AS stage, 1 AS stage_order, COUNT(*)            AS sessions
FROM raw_ga4_sessions
UNION ALL
SELECT
    'Engaged',            2,
    COUNT(CASE WHEN session_duration_s >= 30 OR pageviews > 1 THEN 1 END)
FROM raw_ga4_sessions
UNION ALL
SELECT
    'Multi-page',         3,
    COUNT(CASE WHEN pageviews > 1 THEN 1 END)
FROM raw_ga4_sessions
UNION ALL
SELECT
    'Converted',          4,
    COUNT(CASE WHEN conversions > 0 THEN 1 END)
FROM raw_ga4_sessions
UNION ALL
SELECT
    'Revenue Generated',  5,
    COUNT(CASE WHEN revenue > 0 THEN 1 END)
FROM raw_ga4_sessions
ORDER BY stage_order;


-- 2. Drop-off rate between funnel stages
WITH stages AS (
    SELECT
        SUM(sessions)                                                       AS stage1_landing,
        SUM(CASE WHEN session_duration_s >= 30 OR pageviews > 1 THEN sessions END) AS stage2_engaged,
        SUM(CASE WHEN pageviews > 1 THEN sessions END)                     AS stage3_multipage,
        SUM(conversions)                                                    AS stage4_converted
    FROM raw_ga4_sessions
)
SELECT
    stage1_landing,
    stage2_engaged,
    stage3_multipage,
    stage4_converted,
    ROUND((1 - stage2_engaged::NUMERIC / NULLIF(stage1_landing, 0)) * 100, 1) AS dropoff_1_to_2_pct,
    ROUND((1 - stage3_multipage::NUMERIC / NULLIF(stage2_engaged, 0)) * 100, 1) AS dropoff_2_to_3_pct,
    ROUND((1 - stage4_converted::NUMERIC / NULLIF(stage3_multipage, 0)) * 100, 1) AS dropoff_3_to_4_pct
FROM stages;


-- 3. Funnel completion rate by channel
SELECT
    channel_grouping,
    SUM(sessions)                                                           AS total_sessions,
    SUM(CASE WHEN pageviews > 1 THEN sessions END)                         AS multi_page_sessions,
    SUM(conversions)                                                        AS conversions,
    ROUND(SUM(conversions)::NUMERIC / NULLIF(SUM(sessions), 0) * 100, 2)   AS completion_rate_pct
FROM raw_ga4_sessions
GROUP BY channel_grouping
ORDER BY completion_rate_pct DESC;


-- 4. Funnel performance by device
SELECT
    device_category,
    SUM(sessions)                                                           AS total_sessions,
    ROUND(AVG(pageviews), 2)                                                AS avg_pages_per_session,
    ROUND(100.0 * SUM(CASE WHEN bounce THEN 1 END) / NULLIF(SUM(sessions), 0), 2) AS bounce_rate_pct,
    SUM(conversions)                                                        AS conversions,
    ROUND(SUM(conversions)::NUMERIC / NULLIF(SUM(sessions), 0) * 100, 2)   AS cvr_pct
FROM raw_ga4_sessions
GROUP BY device_category
ORDER BY cvr_pct DESC;


-- 5. Time to convert by channel (avg session duration for converting sessions)
SELECT
    channel_grouping,
    COUNT(CASE WHEN conversions > 0 THEN 1 END)                            AS converting_sessions,
    ROUND(AVG(CASE WHEN conversions > 0 THEN session_duration_s END), 1)   AS avg_time_to_convert_s,
    ROUND(AVG(CASE WHEN conversions > 0 THEN pageviews END), 1)            AS avg_pages_before_convert
FROM raw_ga4_sessions
GROUP BY channel_grouping
ORDER BY avg_time_to_convert_s ASC NULLS LAST;
