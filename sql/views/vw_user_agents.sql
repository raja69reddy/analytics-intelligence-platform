-- vw_user_agents: browser, OS, and device type distribution parsed from raw user_agent strings.
CREATE OR REPLACE VIEW vw_user_agents AS
WITH parsed AS (
    SELECT
        CASE
            WHEN user_agent ILIKE '%Edg/%'     THEN 'Edge'
            WHEN user_agent ILIKE '%Chrome/%'  THEN 'Chrome'
            WHEN user_agent ILIKE '%Firefox/%' THEN 'Firefox'
            WHEN user_agent ILIKE '%Safari/%' AND user_agent NOT ILIKE '%Chrome/%' THEN 'Safari'
            ELSE 'Other'
        END AS browser,
        CASE
            WHEN user_agent ILIKE '%Windows%'   THEN 'Windows'
            WHEN user_agent ILIKE '%Macintosh%' THEN 'macOS'
            WHEN user_agent ILIKE '%Linux%' AND user_agent NOT ILIKE '%Android%' THEN 'Linux'
            WHEN user_agent ILIKE '%Android%'   THEN 'Android'
            WHEN user_agent ILIKE '%iPhone%' OR user_agent ILIKE '%iPad%' THEN 'iOS'
            ELSE 'Other'
        END AS operating_system,
        CASE
            WHEN user_agent ILIKE '%Mobile%' OR user_agent ILIKE '%Android%'
                 OR user_agent ILIKE '%iPhone%' THEN 'mobile'
            WHEN user_agent ILIKE '%Tablet%' OR user_agent ILIKE '%iPad%' THEN 'tablet'
            ELSE 'desktop'
        END AS device_type
    FROM raw_server_logs
    WHERE user_agent IS NOT NULL
),
browser_counts AS (
    SELECT browser, COUNT(*) AS requests FROM parsed GROUP BY browser
),
os_counts AS (
    SELECT operating_system, COUNT(*) AS requests FROM parsed GROUP BY operating_system
),
device_counts AS (
    SELECT device_type, COUNT(*) AS requests FROM parsed GROUP BY device_type
),
total AS (SELECT COUNT(*) AS n FROM parsed)
SELECT
    'browser'          AS dimension,
    browser            AS value,
    requests,
    ROUND(100.0 * requests / NULLIF((SELECT n FROM total), 0), 2) AS share_pct
FROM browser_counts
UNION ALL
SELECT
    'os'               AS dimension,
    operating_system   AS value,
    requests,
    ROUND(100.0 * requests / NULLIF((SELECT n FROM total), 0), 2) AS share_pct
FROM os_counts
UNION ALL
SELECT
    'device'           AS dimension,
    device_type        AS value,
    requests,
    ROUND(100.0 * requests / NULLIF((SELECT n FROM total), 0), 2) AS share_pct
FROM device_counts
ORDER BY dimension, requests DESC;
