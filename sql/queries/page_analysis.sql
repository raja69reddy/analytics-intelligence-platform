-- page_analysis.sql: 5 reusable page-level analysis queries.

-- Query 1: Top 10 pages by total requests
SELECT
    url,
    total_requests,
    unique_visitors,
    avg_response_time_ms,
    error_rate_pct,
    last_visited
FROM vw_top_pages
ORDER BY total_requests DESC
LIMIT 10;

-- Query 2: Slowest 5 pages by average response time
SELECT
    url,
    total_requests,
    avg_response_time_ms,
    p95_response_time_ms,
    slow_requests,
    slow_pct
FROM vw_page_performance
ORDER BY avg_response_time_ms DESC
LIMIT 5;

-- Query 3: Pages with highest error rate (min 50 requests)
SELECT
    url,
    total_requests,
    errors_4xx,
    errors_5xx,
    total_errors,
    error_rate_pct
FROM vw_error_pages
WHERE total_requests >= 50
ORDER BY error_rate_pct DESC
LIMIT 10;

-- Query 4: Most engaging pages by average scroll depth
SELECT
    page_url,
    scroll_events,
    avg_scroll_depth_pct,
    bucket_75_100 AS deep_scroll_events,
    pct_75_100    AS deep_scroll_pct
FROM vw_scroll_depth
ORDER BY avg_scroll_depth_pct DESC
LIMIT 10;

-- Query 5: Pages with most form submissions
SELECT
    page_url,
    total_events,
    form_submit_events,
    ROUND(100.0 * form_submit_events / NULLIF(total_events, 0), 2) AS form_submit_pct,
    unique_sessions
FROM vw_engagement_events
ORDER BY form_submit_events DESC
LIMIT 10;
