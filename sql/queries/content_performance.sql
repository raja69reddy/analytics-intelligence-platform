-- Content Performance Analysis
-- All queries use raw_ga4_sessions and raw_scrape_pages.

-- 1. Top 10 pages by total sessions
SELECT
    landing_page                        AS page,
    SUM(sessions)                       AS total_sessions,
    SUM(pageviews)                      AS total_pageviews,
    ROUND(AVG(session_duration_s), 1)   AS avg_duration_s,
    ROUND(SUM(bounce::INT)::NUMERIC / NULLIF(SUM(sessions), 0) * 100, 2) AS bounce_rate_pct
FROM raw_ga4_sessions
GROUP BY landing_page
ORDER BY total_sessions DESC
LIMIT 10;


-- 2. Top 10 pages by avg time on page
SELECT
    landing_page                        AS page,
    ROUND(AVG(session_duration_s), 1)   AS avg_time_on_page_s,
    SUM(sessions)                       AS total_sessions,
    SUM(pageviews)                      AS total_pageviews
FROM raw_ga4_sessions
WHERE session_duration_s > 0
GROUP BY landing_page
HAVING SUM(sessions) >= 5
ORDER BY avg_time_on_page_s DESC
LIMIT 10;


-- 3. Top 10 pages by conversion rate
SELECT
    landing_page                        AS page,
    SUM(sessions)                       AS total_sessions,
    SUM(conversions)                    AS total_conversions,
    ROUND(SUM(conversions)::NUMERIC / NULLIF(SUM(sessions), 0) * 100, 2) AS conversion_rate_pct,
    SUM(revenue)                        AS total_revenue
FROM raw_ga4_sessions
GROUP BY landing_page
HAVING SUM(sessions) >= 10
ORDER BY conversion_rate_pct DESC
LIMIT 10;


-- 4. Top 10 pages by avg scroll depth (from clickstream events)
SELECT
    ce.page_url                         AS page,
    ROUND(AVG(ce.scroll_depth_pct), 1) AS avg_scroll_depth_pct,
    COUNT(DISTINCT ce.session_id)       AS sessions_with_scroll,
    COUNT(*)                            AS scroll_events
FROM raw_clickstream_events ce
WHERE ce.event_name = 'scroll'
  AND ce.scroll_depth_pct IS NOT NULL
GROUP BY ce.page_url
HAVING COUNT(DISTINCT ce.session_id) >= 3
ORDER BY avg_scroll_depth_pct DESC
LIMIT 10;


-- 5. Worst 10 pages by bounce rate (min 20 sessions)
SELECT
    landing_page                        AS page,
    SUM(sessions)                       AS total_sessions,
    SUM(bounce::INT)                    AS total_bounces,
    ROUND(SUM(bounce::INT)::NUMERIC / NULLIF(SUM(sessions), 0) * 100, 2) AS bounce_rate_pct,
    ROUND(AVG(session_duration_s), 1)   AS avg_duration_s
FROM raw_ga4_sessions
GROUP BY landing_page
HAVING SUM(sessions) >= 20
ORDER BY bounce_rate_pct DESC
LIMIT 10;


-- 6. Pages with highest exit rate (sessions that bounced / total sessions, ordered desc)
WITH page_stats AS (
    SELECT
        landing_page                    AS page,
        SUM(sessions)                   AS total_sessions,
        SUM(bounce::INT)                AS exits,
        ROUND(SUM(bounce::INT)::NUMERIC / NULLIF(SUM(sessions), 0) * 100, 2) AS exit_rate_pct,
        ROUND(AVG(session_duration_s), 1) AS avg_duration_s,
        SUM(conversions)                AS conversions
    FROM raw_ga4_sessions
    GROUP BY landing_page
    HAVING SUM(sessions) >= 10
)
SELECT
    page,
    total_sessions,
    exits,
    exit_rate_pct,
    avg_duration_s,
    conversions,
    CASE
        WHEN exit_rate_pct >= 80 THEN 'critical'
        WHEN exit_rate_pct >= 60 THEN 'high'
        WHEN exit_rate_pct >= 40 THEN 'medium'
        ELSE 'low'
    END AS exit_severity
FROM page_stats
ORDER BY exit_rate_pct DESC
LIMIT 10;
