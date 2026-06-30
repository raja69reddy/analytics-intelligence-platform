-- vw_top_pages: page-level request metrics from server logs, enriched with dim_pages metadata.
-- dim_pages LEFT JOIN so view returns data even when dim_pages is empty.
CREATE OR REPLACE VIEW vw_top_pages AS
SELECT
    s.url,
    COALESCE(p.page_title,   s.url)   AS page_title,
    COALESCE(p.page_section, 'unknown') AS page_section,
    COUNT(*)                           AS total_requests,
    COUNT(DISTINCT s.ip_address)       AS unique_visitors,
    ROUND(AVG(s.response_time_ms)::numeric, 2)  AS avg_response_time_ms,
    ROUND(
        100.0 * COUNT(CASE WHEN s.status_code >= 400 THEN 1 END)
        / NULLIF(COUNT(*), 0), 2
    )                                  AS error_rate_pct,
    MAX(s.log_time)                    AS last_visited
FROM raw_server_logs s
LEFT JOIN dim_pages p ON p.url_path = s.url
GROUP BY s.url, p.page_title, p.page_section
ORDER BY total_requests DESC;
