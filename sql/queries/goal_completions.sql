-- ============================================================
-- Goal Completions Analysis
-- Source: raw_ga4_sessions
-- ============================================================


-- 1. Total goal completions by date
SELECT
    session_date,
    SUM(sessions)     AS total_sessions,
    SUM(conversions)  AS goal_completions,
    SUM(revenue)      AS revenue
FROM raw_ga4_sessions
GROUP BY session_date
ORDER BY session_date;


-- 2. Goal completions by source and medium
SELECT
    source,
    medium,
    SUM(sessions)                                                           AS total_sessions,
    SUM(conversions)                                                        AS goal_completions,
    ROUND(SUM(conversions)::NUMERIC / NULLIF(SUM(sessions), 0) * 100, 2)   AS completion_rate_pct,
    SUM(revenue)                                                            AS revenue
FROM raw_ga4_sessions
GROUP BY source, medium
ORDER BY goal_completions DESC
LIMIT 20;


-- 3. Goal completions by channel
SELECT
    channel_grouping,
    SUM(sessions)                                                           AS total_sessions,
    SUM(conversions)                                                        AS goal_completions,
    ROUND(SUM(conversions)::NUMERIC / NULLIF(SUM(sessions), 0) * 100, 2)   AS completion_rate_pct,
    SUM(revenue)                                                            AS revenue,
    ROUND(SUM(revenue) / NULLIF(SUM(conversions), 0), 2)                   AS revenue_per_goal
FROM raw_ga4_sessions
GROUP BY channel_grouping
ORDER BY goal_completions DESC;


-- 4. Goal completion rate by landing page
SELECT
    landing_page,
    SUM(sessions)                                                           AS total_sessions,
    SUM(conversions)                                                        AS goal_completions,
    ROUND(SUM(conversions)::NUMERIC / NULLIF(SUM(sessions), 0) * 100, 2)   AS completion_rate_pct
FROM raw_ga4_sessions
WHERE landing_page IS NOT NULL
GROUP BY landing_page
HAVING SUM(sessions) >= 10
ORDER BY completion_rate_pct DESC
LIMIT 20;


-- 5. Top 10 pages by goal completions
SELECT
    landing_page                                                            AS page,
    SUM(conversions)                                                        AS goal_completions,
    SUM(sessions)                                                           AS total_sessions,
    ROUND(SUM(conversions)::NUMERIC / NULLIF(SUM(sessions), 0) * 100, 2)   AS completion_rate_pct,
    SUM(revenue)                                                            AS revenue
FROM raw_ga4_sessions
WHERE landing_page IS NOT NULL
GROUP BY landing_page
ORDER BY goal_completions DESC
LIMIT 10;
