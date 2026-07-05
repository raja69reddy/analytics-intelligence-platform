-- Session Quality Analysis Queries
-- Uses raw_ga4_sessions and raw_clickstream_events.

-- 1. High quality sessions — duration > 3 min AND bounce = false
SELECT
    session_date,
    COUNT(*) AS high_quality_sessions,
    ROUND(AVG(session_duration_s), 1) AS avg_duration_s,
    ROUND(AVG(pageviews), 2)          AS avg_pageviews
FROM raw_ga4_sessions
WHERE session_duration_s > 180
  AND NOT bounce
GROUP BY session_date
ORDER BY session_date;


-- 2. Low quality sessions — duration < 30s OR bounce = true
SELECT
    session_date,
    COUNT(*) AS low_quality_sessions,
    ROUND(AVG(session_duration_s), 1) AS avg_duration_s,
    ROUND(AVG(pageviews), 2)          AS avg_pageviews
FROM raw_ga4_sessions
WHERE session_duration_s < 30
   OR bounce
GROUP BY session_date
ORDER BY session_date;


-- 3. Session quality score by channel (ratio of high-quality to total)
WITH quality AS (
    SELECT
        channel_grouping,
        COUNT(*) AS total_sessions,
        COUNT(CASE WHEN session_duration_s > 180 AND NOT bounce THEN 1 END) AS high_quality,
        COUNT(CASE WHEN session_duration_s < 30 OR bounce THEN 1 END) AS low_quality
    FROM raw_ga4_sessions
    GROUP BY channel_grouping
)
SELECT
    channel_grouping,
    total_sessions,
    high_quality,
    low_quality,
    ROUND(high_quality::NUMERIC / NULLIF(total_sessions, 0) * 100, 2) AS high_quality_pct,
    ROUND(low_quality::NUMERIC  / NULLIF(total_sessions, 0) * 100, 2) AS low_quality_pct
FROM quality
ORDER BY high_quality_pct DESC;


-- 4. Session quality trend over time (weekly)
WITH weekly AS (
    SELECT
        DATE_TRUNC('week', session_date)::DATE AS week_start,
        COUNT(*) AS total_sessions,
        COUNT(CASE WHEN session_duration_s > 180 AND NOT bounce THEN 1 END) AS high_quality,
        COUNT(CASE WHEN session_duration_s < 30 OR bounce THEN 1 END) AS low_quality
    FROM raw_ga4_sessions
    GROUP BY week_start
)
SELECT
    week_start,
    total_sessions,
    high_quality,
    low_quality,
    ROUND(high_quality::NUMERIC / NULLIF(total_sessions, 0) * 100, 2) AS high_quality_pct,
    ROUND(low_quality::NUMERIC  / NULLIF(total_sessions, 0) * 100, 2) AS low_quality_pct
FROM weekly
ORDER BY week_start;


-- 5. Best time of day for high quality sessions (by hour from server logs)
SELECT
    EXTRACT(HOUR FROM sl.log_time)::INT AS hour_of_day,
    COUNT(*) AS requests,
    ROUND(AVG(sl.response_time_ms), 1) AS avg_response_ms
FROM raw_server_logs sl
WHERE sl.status_code = 200
GROUP BY hour_of_day
ORDER BY requests DESC;


-- 6. Best day of week for high quality sessions
SELECT
    CASE EXTRACT(DOW FROM session_date)::INT
        WHEN 0 THEN 'Sunday'
        WHEN 1 THEN 'Monday'
        WHEN 2 THEN 'Tuesday'
        WHEN 3 THEN 'Wednesday'
        WHEN 4 THEN 'Thursday'
        WHEN 5 THEN 'Friday'
        WHEN 6 THEN 'Saturday'
    END AS day_of_week,
    EXTRACT(DOW FROM session_date)::INT AS dow_num,
    COUNT(*) AS total_sessions,
    COUNT(CASE WHEN session_duration_s > 180 AND NOT bounce THEN 1 END) AS high_quality,
    ROUND(
        COUNT(CASE WHEN session_duration_s > 180 AND NOT bounce THEN 1 END)::NUMERIC
        / NULLIF(COUNT(*), 0) * 100, 2
    ) AS high_quality_pct,
    ROUND(AVG(session_duration_s), 1) AS avg_duration_s
FROM raw_ga4_sessions
GROUP BY dow_num, day_of_week
ORDER BY high_quality_pct DESC;
