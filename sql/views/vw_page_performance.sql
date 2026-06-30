-- vw_page_performance: response time distribution per page.
-- Classifies requests as fast (<200ms), normal (200-1000ms), or slow (>1000ms).
CREATE OR REPLACE VIEW vw_page_performance AS
WITH page_stats AS (
    SELECT
        url,
        COUNT(*)                                                           AS total_requests,
        ROUND(AVG(response_time_ms)::numeric, 2)                           AS avg_response_time_ms,
        ROUND(MIN(response_time_ms)::numeric, 2)                           AS min_response_time_ms,
        ROUND(MAX(response_time_ms)::numeric, 2)                           AS max_response_time_ms,
        ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY response_time_ms)::numeric, 2)
                                                                           AS p50_response_time_ms,
        ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY response_time_ms)::numeric, 2)
                                                                           AS p95_response_time_ms,
        COUNT(CASE WHEN response_time_ms < 200  THEN 1 END)               AS fast_requests,
        COUNT(CASE WHEN response_time_ms BETWEEN 200 AND 1000 THEN 1 END) AS normal_requests,
        COUNT(CASE WHEN response_time_ms > 1000 THEN 1 END)               AS slow_requests
    FROM raw_server_logs
    WHERE response_time_ms IS NOT NULL
    GROUP BY url
)
SELECT
    url,
    total_requests,
    avg_response_time_ms,
    min_response_time_ms,
    max_response_time_ms,
    p50_response_time_ms,
    p95_response_time_ms,
    fast_requests,
    normal_requests,
    slow_requests,
    ROUND(100.0 * fast_requests   / NULLIF(total_requests, 0), 2) AS fast_pct,
    ROUND(100.0 * normal_requests / NULLIF(total_requests, 0), 2) AS normal_pct,
    ROUND(100.0 * slow_requests   / NULLIF(total_requests, 0), 2) AS slow_pct
FROM page_stats
ORDER BY avg_response_time_ms DESC;
