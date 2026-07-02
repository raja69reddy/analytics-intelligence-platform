-- Funnel Drop-off Analysis
-- Each query drills into where users leave the conversion funnel.

-- 1. Stage-by-stage drop-off with completion rates
WITH stages AS (
    SELECT 'Landing'   AS stage, 1 AS stage_order,
           COUNT(*)                                                           AS users_entering,
           AVG(session_duration_s)                                           AS avg_time_s
    FROM raw_ga4_sessions
    UNION ALL
    SELECT 'Engaged', 2,
           COUNT(CASE WHEN session_duration_s >= 30 OR pageviews > 1 THEN 1 END),
           AVG(CASE WHEN session_duration_s >= 30 OR pageviews > 1 THEN session_duration_s END)
    FROM raw_ga4_sessions
    UNION ALL
    SELECT 'Multi-page', 3,
           COUNT(CASE WHEN pageviews >= 3 THEN 1 END),
           AVG(CASE WHEN pageviews >= 3 THEN session_duration_s END)
    FROM raw_ga4_sessions
    UNION ALL
    SELECT 'Converted', 4,
           COUNT(CASE WHEN conversions > 0 THEN 1 END),
           AVG(CASE WHEN conversions > 0 THEN session_duration_s END)
    FROM raw_ga4_sessions
    UNION ALL
    SELECT 'Revenue', 5,
           COUNT(CASE WHEN revenue > 0 THEN 1 END),
           AVG(CASE WHEN revenue > 0 THEN session_duration_s END)
    FROM raw_ga4_sessions
)
SELECT
    stage,
    stage_order,
    users_entering,
    LAG(users_entering) OVER (ORDER BY stage_order) AS prev_stage_users,
    users_entering - LAG(users_entering) OVER (ORDER BY stage_order) AS users_dropped,
    ROUND(
        (1 - users_entering::NUMERIC / NULLIF(LAG(users_entering) OVER (ORDER BY stage_order), 0)) * 100,
        2
    ) AS dropoff_pct,
    ROUND(
        users_entering::NUMERIC / NULLIF(FIRST_VALUE(users_entering) OVER (ORDER BY stage_order), 0) * 100,
        2
    ) AS completion_rate_pct,
    ROUND(avg_time_s, 1) AS avg_time_at_stage_s
FROM stages
ORDER BY stage_order;


-- 2. Drop-off percentage between consecutive stages
WITH stage_counts AS (
    SELECT
        SUM(sessions)                                                        AS landing,
        SUM(CASE WHEN session_duration_s >= 30 OR pageviews > 1 THEN sessions END) AS engaged,
        SUM(CASE WHEN pageviews >= 3 THEN sessions END)                      AS multi_page,
        SUM(CASE WHEN conversions > 0 THEN sessions END)                     AS converted,
        SUM(CASE WHEN revenue > 0 THEN sessions END)                         AS revenue
    FROM raw_ga4_sessions
)
SELECT
    'Landing → Engaged'    AS transition,
    ROUND((1 - engaged::NUMERIC / NULLIF(landing, 0)) * 100, 2)    AS dropoff_pct
FROM stage_counts
UNION ALL
SELECT 'Engaged → Multi-page',
    ROUND((1 - multi_page::NUMERIC / NULLIF(engaged, 0)) * 100, 2)
FROM stage_counts
UNION ALL
SELECT 'Multi-page → Converted',
    ROUND((1 - converted::NUMERIC / NULLIF(multi_page, 0)) * 100, 2)
FROM stage_counts
UNION ALL
SELECT 'Converted → Revenue',
    ROUND((1 - revenue::NUMERIC / NULLIF(converted, 0)) * 100, 2)
FROM stage_counts;


-- 3. Best performing channel at each funnel stage (highest conversion rate)
SELECT
    channel_grouping,
    COUNT(*)                                                                              AS landing_sessions,
    COUNT(CASE WHEN session_duration_s >= 30 OR pageviews > 1 THEN 1 END)                AS engaged,
    COUNT(CASE WHEN pageviews >= 3 THEN 1 END)                                           AS multi_page,
    COUNT(CASE WHEN conversions > 0 THEN 1 END)                                          AS converted,
    ROUND(COUNT(CASE WHEN conversions > 0 THEN 1 END)::NUMERIC / NULLIF(COUNT(*), 0) * 100, 2) AS conversion_rate_pct,
    ROUND(COUNT(CASE WHEN session_duration_s >= 30 OR pageviews > 1 THEN 1 END)::NUMERIC
          / NULLIF(COUNT(*), 0) * 100, 2)                                                AS engagement_rate_pct
FROM raw_ga4_sessions
GROUP BY channel_grouping
ORDER BY conversion_rate_pct DESC;


-- 4. Avg time spent at each stage by device
SELECT
    device_category,
    ROUND(AVG(session_duration_s), 1)                                        AS avg_total_time_s,
    ROUND(AVG(CASE WHEN session_duration_s >= 30 OR pageviews > 1 THEN session_duration_s END), 1) AS avg_engaged_time_s,
    ROUND(AVG(CASE WHEN pageviews >= 3 THEN session_duration_s END), 1)      AS avg_multipage_time_s,
    ROUND(AVG(CASE WHEN conversions > 0 THEN session_duration_s END), 1)     AS avg_converted_time_s
FROM raw_ga4_sessions
GROUP BY device_category
ORDER BY avg_total_time_s DESC;


-- 5. Funnel completion rate by landing page (top 20 pages)
SELECT
    landing_page,
    COUNT(*)                                                                  AS landing_sessions,
    ROUND(COUNT(CASE WHEN session_duration_s >= 30 OR pageviews > 1 THEN 1 END)::NUMERIC
          / NULLIF(COUNT(*), 0) * 100, 2)                                    AS engagement_rate_pct,
    ROUND(COUNT(CASE WHEN pageviews >= 3 THEN 1 END)::NUMERIC
          / NULLIF(COUNT(*), 0) * 100, 2)                                    AS multipage_rate_pct,
    ROUND(COUNT(CASE WHEN conversions > 0 THEN 1 END)::NUMERIC
          / NULLIF(COUNT(*), 0) * 100, 2)                                    AS conversion_rate_pct
FROM raw_ga4_sessions
GROUP BY landing_page
HAVING COUNT(*) >= 5
ORDER BY conversion_rate_pct DESC
LIMIT 20;
