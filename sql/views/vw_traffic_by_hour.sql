-- vw_traffic_by_hour: request volume, response time, and error rate by hour of day.
CREATE OR REPLACE VIEW vw_traffic_by_hour AS
WITH hourly AS (
    SELECT
        EXTRACT(HOUR FROM log_time)::int                              AS hour_of_day,
        COUNT(*)                                                      AS total_requests,
        COUNT(DISTINCT ip_address)                                    AS unique_visitors,
        ROUND(AVG(response_time_ms)::numeric, 2)                      AS avg_response_time_ms,
        COUNT(CASE WHEN status_code >= 400 THEN 1 END)               AS error_requests,
        ROUND(
            100.0 * COUNT(CASE WHEN status_code >= 400 THEN 1 END)
            / NULLIF(COUNT(*), 0), 2
        )                                                             AS error_rate_pct
    FROM raw_server_logs
    GROUP BY EXTRACT(HOUR FROM log_time)
)
SELECT
    hour_of_day,
    total_requests,
    unique_visitors,
    avg_response_time_ms,
    error_requests,
    error_rate_pct,
    RANK() OVER (ORDER BY total_requests DESC)                        AS traffic_rank
FROM hourly
ORDER BY hour_of_day;
