-- ============================================================
-- Conversion Deep Dive
-- Sources: vw_conversions, raw_clickstream_events (event_name,
--          page_url, event_time), raw_ga4_sessions (device_category,
--          landing_page, conversions, sessions)
-- ============================================================


-- 1. Conversion rate by landing page
--    Landing page and conversion flag come directly from
--    raw_ga4_sessions which tracks entry URLs per session.
SELECT
    landing_page,
    SUM(sessions)                                                           AS total_sessions,
    SUM(conversions)                                                        AS goal_completions,
    ROUND(SUM(conversions)::NUMERIC / NULLIF(SUM(sessions), 0) * 100, 2)   AS cvr_pct,
    ROUND(SUM(revenue)::NUMERIC, 2)                                         AS total_revenue
FROM raw_ga4_sessions
WHERE landing_page IS NOT NULL
GROUP BY landing_page
HAVING SUM(sessions) >= 10
ORDER BY cvr_pct DESC
LIMIT 25;


-- 2. Conversion rate by traffic source
SELECT
    source,
    medium,
    channel_grouping,
    SUM(sessions)                                                           AS total_sessions,
    SUM(goal_completions)                                                   AS goal_completions,
    ROUND(
        SUM(goal_completions)::NUMERIC / NULLIF(SUM(sessions), 0) * 100,
    2)                                                                      AS cvr_pct,
    ROUND(SUM(revenue)::NUMERIC, 2)                                         AS total_revenue
FROM vw_conversions
GROUP BY source, medium, channel_grouping
ORDER BY cvr_pct DESC
LIMIT 30;


-- 3. Conversion rate by device type AND channel combined
SELECT
    device_category,
    channel_grouping,
    SUM(sessions)                                                           AS total_sessions,
    SUM(conversions)                                                        AS goal_completions,
    ROUND(
        SUM(conversions)::NUMERIC / NULLIF(SUM(sessions), 0) * 100,
    2)                                                                      AS cvr_pct,
    ROUND(SUM(revenue)::NUMERIC, 2)                                         AS revenue
FROM raw_ga4_sessions
GROUP BY device_category, channel_grouping
HAVING SUM(sessions) > 0
ORDER BY channel_grouping, device_category;


-- 4. Time between first session and conversion (days span per channel)
--    Uses the earliest and latest session dates from vw_conversions
--    as a proxy for first-touch to last-touch lag.
WITH channel_dates AS (
    SELECT
        channel_grouping,
        MIN(session_date)                                                   AS first_session_date,
        MAX(session_date)                                                   AS last_conv_date,
        COUNT(DISTINCT session_date)                                        AS active_days,
        SUM(sessions)                                                       AS total_sessions,
        SUM(goal_completions)                                               AS total_conversions
    FROM vw_conversions
    WHERE goal_completions > 0
    GROUP BY channel_grouping
)
SELECT
    channel_grouping,
    first_session_date,
    last_conv_date,
    (last_conv_date - first_session_date)                                   AS days_span,
    active_days,
    total_sessions,
    total_conversions,
    ROUND(
        (last_conv_date - first_session_date)::NUMERIC
        / NULLIF(active_days, 0),
    1)                                                                      AS avg_days_between_active_sessions
FROM channel_dates
ORDER BY days_span DESC;


-- 5. Average pages visited before converting
--    Counts distinct page_url values seen in a converting session
--    before the first form_submit event_time.
WITH first_submit AS (
    SELECT
        session_id,
        MIN(event_time)                                                     AS submit_time
    FROM raw_clickstream_events
    WHERE event_name = 'form_submit'
    GROUP BY session_id
),
pre_conv_pages AS (
    SELECT
        ce.session_id,
        COUNT(DISTINCT ce.page_url)                                         AS pages_before_conversion
    FROM raw_clickstream_events ce
    JOIN first_submit fs ON fs.session_id = ce.session_id
    WHERE ce.event_time <= fs.submit_time
      AND ce.event_name   != 'form_submit'
    GROUP BY ce.session_id
)
SELECT
    ROUND(AVG(pages_before_conversion), 2)                                  AS avg_pages_before_conversion,
    MIN(pages_before_conversion)                                            AS min_pages,
    MAX(pages_before_conversion)                                            AS max_pages,
    PERCENTILE_CONT(0.5) WITHIN GROUP (
        ORDER BY pages_before_conversion
    )::NUMERIC                                                              AS median_pages,
    COUNT(*)                                                                AS converting_sessions
FROM pre_conv_pages;
