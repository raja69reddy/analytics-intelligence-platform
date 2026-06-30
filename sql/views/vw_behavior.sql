-- vw_behavior: per-page behavior combining server request metrics with clickstream engagement.
-- Shows top pages, response time, error rate, scroll depth, and event type breakdown.
CREATE OR REPLACE VIEW vw_behavior AS
WITH server_stats AS (
    SELECT
        url                                                          AS page,
        COUNT(*)                                                     AS total_requests,
        COUNT(CASE WHEN status_code = 200 THEN 1 END)               AS ok_count,
        COUNT(CASE WHEN status_code BETWEEN 400 AND 599 THEN 1 END) AS error_count,
        ROUND(
            100.0 * COUNT(CASE WHEN status_code BETWEEN 400 AND 599 THEN 1 END)
            / NULLIF(COUNT(*), 0), 2
        )                                                            AS error_rate_pct,
        ROUND(AVG(response_time_ms)::numeric, 0)                    AS avg_response_ms,
        ROUND(SUM(response_bytes) / 1048576.0, 2)                   AS total_mb_served
    FROM raw_server_logs
    GROUP BY url
),
click_stats AS (
    -- Scroll depth averages by page from clickstream
    SELECT
        page_url,
        COUNT(*)                                                      AS total_events,
        COUNT(CASE WHEN event_name = 'click'       THEN 1 END)       AS clicks,
        COUNT(CASE WHEN event_name = 'scroll'      THEN 1 END)       AS scrolls,
        COUNT(CASE WHEN event_name = 'pageview'    THEN 1 END)       AS pageviews,
        COUNT(CASE WHEN event_name = 'form_submit' THEN 1 END)       AS form_submits,
        ROUND(AVG(CASE WHEN event_name = 'scroll'
                       THEN scroll_depth_pct END)::numeric, 1)       AS avg_scroll_depth_pct,
        ROUND(
            100.0 * COUNT(CASE WHEN event_name IN ('click','form_submit') THEN 1 END)
            / NULLIF(COUNT(*), 0), 1
        )                                                             AS engagement_rate_pct
    FROM raw_clickstream_events
    GROUP BY page_url
),
-- Top pages by engagement score (scroll + click / total events)
engagement AS (
    SELECT
        page_url,
        ROUND(
            (COALESCE(avg_scroll_depth_pct, 0) / 100.0) * 0.5
            + (engagement_rate_pct / 100.0) * 0.5, 3
        ) AS engagement_score
    FROM click_stats
)
SELECT
    s.page,
    s.total_requests,
    s.ok_count,
    s.error_count,
    s.error_rate_pct,
    s.avg_response_ms,
    s.total_mb_served,
    COALESCE(c.total_events,          0) AS total_events,
    COALESCE(c.clicks,                0) AS clicks,
    COALESCE(c.scrolls,               0) AS scrolls,
    COALESCE(c.pageviews,             0) AS pageviews,
    COALESCE(c.form_submits,          0) AS form_submits,
    c.avg_scroll_depth_pct,
    COALESCE(c.engagement_rate_pct,   0) AS engagement_rate_pct,
    COALESCE(e.engagement_score,      0) AS engagement_score
FROM server_stats s
LEFT JOIN click_stats c  ON RTRIM(c.page_url, '/') = s.page
LEFT JOIN engagement  e  ON RTRIM(e.page_url, '/') = s.page
ORDER BY s.total_requests DESC;


-- vw_funnel: session funnel using raw GA4 data (landing -> engagement -> conversion).
CREATE OR REPLACE VIEW vw_funnel AS
SELECT
    session_date,
    channel_grouping,
    SUM(sessions)                                   AS step1_sessions,
    SUM(new_users)                                  AS step2_new_users,
    SUM(CASE WHEN bounce = FALSE THEN sessions END) AS step3_engaged,
    COUNT(DISTINCT session_date)                    AS active_days
FROM raw_ga4_sessions
GROUP BY session_date, channel_grouping
ORDER BY session_date;
