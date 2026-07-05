-- User Behavior Analysis Queries
-- Uses raw_ga4_sessions and raw_clickstream_events.

-- 1. Avg time on page by page type (URL depth)
SELECT
    CASE
        WHEN landing_page ~ '^https?://[^/]+/?$'             THEN 'homepage'
        WHEN landing_page ~ '^https?://[^/]+/[^/]+/?$'       THEN 'top_level'
        WHEN landing_page ~ '^https?://[^/]+/[^/]+/[^/]+/?$' THEN 'second_level'
        ELSE 'deep'
    END AS page_type,
    COUNT(*) AS sessions,
    ROUND(AVG(session_duration_s), 1) AS avg_time_on_page_s,
    ROUND(AVG(pageviews), 2)          AS avg_pageviews,
    ROUND(SUM(bounce::INT)::NUMERIC / NULLIF(COUNT(*), 0) * 100, 2) AS bounce_rate_pct
FROM raw_ga4_sessions
GROUP BY page_type
ORDER BY avg_time_on_page_s DESC;


-- 2. Avg scroll depth by device type (from clickstream events)
SELECT
    ce.device_category,
    ROUND(AVG(ce.scroll_depth_pct), 1) AS avg_scroll_depth_pct,
    COUNT(DISTINCT ce.session_id)      AS sessions_with_scroll,
    COUNT(*)                           AS scroll_events
FROM raw_clickstream_events ce
WHERE ce.event_name = 'scroll'
  AND ce.scroll_depth_pct IS NOT NULL
GROUP BY ce.device_category
ORDER BY avg_scroll_depth_pct DESC;


-- 3. Avg session duration by channel
SELECT
    channel_grouping,
    COUNT(*) AS sessions,
    ROUND(AVG(session_duration_s), 1) AS avg_session_s,
    ROUND(AVG(pageviews), 2)          AS avg_pageviews,
    ROUND(SUM(bounce::INT)::NUMERIC / NULLIF(COUNT(*), 0) * 100, 2) AS bounce_rate_pct
FROM raw_ga4_sessions
GROUP BY channel_grouping
ORDER BY avg_session_s DESC;


-- 4. Pages with highest engagement score
-- Engagement = long duration + multiple pages + low bounce
WITH page_metrics AS (
    SELECT
        landing_page,
        COUNT(*) AS sessions,
        ROUND(AVG(session_duration_s), 1)  AS avg_duration_s,
        ROUND(AVG(pageviews), 2)           AS avg_pageviews,
        ROUND(SUM(bounce::INT)::NUMERIC / NULLIF(COUNT(*), 0) * 100, 2) AS bounce_rate_pct
    FROM raw_ga4_sessions
    GROUP BY landing_page
    HAVING COUNT(*) >= 10
)
SELECT
    landing_page,
    sessions,
    avg_duration_s,
    avg_pageviews,
    bounce_rate_pct,
    ROUND(
        LEAST(avg_duration_s / 300.0, 1) * 40
        + LEAST((avg_pageviews - 1) / 4.0, 1) * 30
        + (1 - bounce_rate_pct / 100.0) * 30
    , 2) AS engagement_score
FROM page_metrics
ORDER BY engagement_score DESC
LIMIT 10;


-- 5. Pages with lowest engagement score
WITH page_metrics AS (
    SELECT
        landing_page,
        COUNT(*) AS sessions,
        ROUND(AVG(session_duration_s), 1)  AS avg_duration_s,
        ROUND(AVG(pageviews), 2)           AS avg_pageviews,
        ROUND(SUM(bounce::INT)::NUMERIC / NULLIF(COUNT(*), 0) * 100, 2) AS bounce_rate_pct
    FROM raw_ga4_sessions
    GROUP BY landing_page
    HAVING COUNT(*) >= 10
)
SELECT
    landing_page,
    sessions,
    avg_duration_s,
    avg_pageviews,
    bounce_rate_pct,
    ROUND(
        LEAST(avg_duration_s / 300.0, 1) * 40
        + LEAST((avg_pageviews - 1) / 4.0, 1) * 30
        + (1 - bounce_rate_pct / 100.0) * 30
    , 2) AS engagement_score
FROM page_metrics
ORDER BY engagement_score ASC
LIMIT 10;


-- 6. User journey: most common entry landing pages (top sequences approximated by page pairs)
SELECT
    landing_page        AS entry_page,
    COUNT(*)            AS sessions,
    SUM(pageviews)      AS total_pageviews,
    ROUND(AVG(session_duration_s), 1) AS avg_duration_s,
    ROUND(SUM(bounce::INT)::NUMERIC / NULLIF(COUNT(*), 0) * 100, 2) AS exit_rate_pct
FROM raw_ga4_sessions
GROUP BY landing_page
ORDER BY sessions DESC
LIMIT 20;


-- 7. Drop-off pages — highest exit rate (bounced / total sessions, min 10 sessions)
SELECT
    landing_page,
    COUNT(*)                                                                    AS sessions,
    SUM(bounce::INT)                                                            AS exits,
    ROUND(SUM(bounce::INT)::NUMERIC / NULLIF(COUNT(*), 0) * 100, 2)           AS exit_rate_pct,
    ROUND(AVG(session_duration_s), 1)                                          AS avg_duration_s
FROM raw_ga4_sessions
GROUP BY landing_page
HAVING COUNT(*) >= 10
ORDER BY exit_rate_pct DESC
LIMIT 10;


-- 8. Sticky pages — pages users return to most (high sessions with low new_users ratio)
SELECT
    landing_page,
    SUM(sessions)   AS total_sessions,
    SUM(new_users)  AS new_user_sessions,
    SUM(sessions) - SUM(new_users) AS returning_sessions,
    ROUND((SUM(sessions) - SUM(new_users))::NUMERIC / NULLIF(SUM(sessions), 0) * 100, 2) AS returning_pct,
    ROUND(AVG(session_duration_s), 1) AS avg_duration_s
FROM raw_ga4_sessions
GROUP BY landing_page
HAVING SUM(sessions) >= 10
ORDER BY returning_pct DESC
LIMIT 10;
