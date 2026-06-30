-- vw_behavior: per-page behavior metrics sourced from raw_server_logs.
-- Shows top pages, average response time, and error rate per page.
CREATE OR REPLACE VIEW vw_behavior AS
SELECT
    url                                                          AS page,
    COUNT(*)                                                     AS total_requests,
    COUNT(CASE WHEN method = 'GET' THEN 1 END)                  AS get_requests,
    COUNT(CASE WHEN status_code = 200 THEN 1 END)               AS ok_count,
    COUNT(CASE WHEN status_code BETWEEN 400 AND 599 THEN 1 END) AS error_count,
    ROUND(
        100.0 * COUNT(CASE WHEN status_code BETWEEN 400 AND 599 THEN 1 END)
        / NULLIF(COUNT(*), 0), 2
    )                                                            AS error_rate_pct,
    ROUND(AVG(response_time_ms)::numeric, 0)                    AS avg_response_ms,
    ROUND(MIN(response_time_ms)::numeric, 0)                    AS min_response_ms,
    ROUND(MAX(response_time_ms)::numeric, 0)                    AS max_response_ms,
    ROUND(SUM(response_bytes) / 1048576.0, 2)                   AS total_mb_served
FROM raw_server_logs
GROUP BY url
ORDER BY total_requests DESC;


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
