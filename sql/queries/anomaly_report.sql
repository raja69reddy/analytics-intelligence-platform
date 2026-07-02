-- Anomaly Report SQL Queries
-- Detects statistical outliers in traffic, bounce rate, and conversion rate.

-- 1. Days where sessions deviate more than 2 standard deviations from mean
WITH daily_sessions AS (
    SELECT
        session_date,
        SUM(sessions) AS daily_sessions
    FROM raw_ga4_sessions
    GROUP BY session_date
),
stats AS (
    SELECT
        AVG(daily_sessions)    AS mean_sessions,
        STDDEV(daily_sessions) AS stddev_sessions
    FROM daily_sessions
)
SELECT
    d.session_date,
    d.daily_sessions,
    ROUND(s.mean_sessions, 0)    AS mean_sessions,
    ROUND(s.stddev_sessions, 0)  AS stddev_sessions,
    ROUND((d.daily_sessions - s.mean_sessions) / NULLIF(s.stddev_sessions, 0), 2) AS z_score,
    CASE
        WHEN ABS((d.daily_sessions - s.mean_sessions) / NULLIF(s.stddev_sessions, 0)) >= 3 THEN 'critical'
        WHEN ABS((d.daily_sessions - s.mean_sessions) / NULLIF(s.stddev_sessions, 0)) >= 2 THEN 'warning'
        ELSE 'normal'
    END AS severity
FROM daily_sessions d CROSS JOIN stats s
WHERE ABS((d.daily_sessions - s.mean_sessions) / NULLIF(s.stddev_sessions, 0)) >= 2
ORDER BY d.session_date;


-- 2. Days where bounce rate spikes above threshold (mean + 1.5 stddev)
WITH daily_bounce AS (
    SELECT
        session_date,
        ROUND(SUM(bounce::INT)::NUMERIC / NULLIF(SUM(sessions), 0) * 100, 2) AS bounce_rate_pct
    FROM raw_ga4_sessions
    GROUP BY session_date
),
stats AS (
    SELECT
        AVG(bounce_rate_pct)    AS mean_bounce,
        STDDEV(bounce_rate_pct) AS stddev_bounce
    FROM daily_bounce
)
SELECT
    d.session_date,
    d.bounce_rate_pct,
    ROUND(s.mean_bounce, 2)   AS mean_bounce_pct,
    ROUND(s.mean_bounce + 1.5 * s.stddev_bounce, 2) AS threshold_pct,
    ROUND((d.bounce_rate_pct - s.mean_bounce) / NULLIF(s.stddev_bounce, 0), 2) AS z_score,
    'Bounce rate spike' AS anomaly_type,
    'Review traffic sources and landing page changes on this date' AS recommended_action
FROM daily_bounce d CROSS JOIN stats s
WHERE d.bounce_rate_pct > s.mean_bounce + 1.5 * s.stddev_bounce
ORDER BY d.session_date;


-- 3. Days where conversion rate drops below threshold (mean - 1.5 stddev)
WITH daily_cvr AS (
    SELECT
        session_date,
        ROUND(SUM(conversions)::NUMERIC / NULLIF(SUM(sessions), 0) * 100, 4) AS cvr_pct
    FROM raw_ga4_sessions
    GROUP BY session_date
),
stats AS (
    SELECT
        AVG(cvr_pct)    AS mean_cvr,
        STDDEV(cvr_pct) AS stddev_cvr
    FROM daily_cvr
)
SELECT
    d.session_date,
    d.cvr_pct,
    ROUND(s.mean_cvr, 4)   AS mean_cvr_pct,
    ROUND(s.mean_cvr - 1.5 * s.stddev_cvr, 4) AS threshold_pct,
    ROUND((d.cvr_pct - s.mean_cvr) / NULLIF(s.stddev_cvr, 0), 2) AS z_score,
    'Conversion rate drop' AS anomaly_type,
    'Check checkout flow, payment gateway, and campaign performance' AS recommended_action
FROM daily_cvr d CROSS JOIN stats s
WHERE d.cvr_pct < s.mean_cvr - 1.5 * s.stddev_cvr
ORDER BY d.session_date;


-- 4. Anomaly severity scoring — all anomaly types in one view
WITH daily AS (
    SELECT
        session_date,
        SUM(sessions)  AS daily_sessions,
        ROUND(SUM(bounce::INT)::NUMERIC / NULLIF(SUM(sessions), 0) * 100, 2) AS bounce_rate_pct,
        ROUND(SUM(conversions)::NUMERIC / NULLIF(SUM(sessions), 0) * 100, 4) AS cvr_pct
    FROM raw_ga4_sessions
    GROUP BY session_date
),
global_stats AS (
    SELECT
        AVG(daily_sessions)    AS mean_s, STDDEV(daily_sessions)    AS std_s,
        AVG(bounce_rate_pct)   AS mean_b, STDDEV(bounce_rate_pct)   AS std_b,
        AVG(cvr_pct)           AS mean_c, STDDEV(cvr_pct)           AS std_c
    FROM daily
),
scored AS (
    SELECT
        d.session_date,
        d.daily_sessions,
        d.bounce_rate_pct,
        d.cvr_pct,
        ABS((d.daily_sessions  - g.mean_s) / NULLIF(g.std_s, 0)) AS sessions_z,
        ABS((d.bounce_rate_pct - g.mean_b) / NULLIF(g.std_b, 0)) AS bounce_z,
        ABS((d.cvr_pct         - g.mean_c) / NULLIF(g.std_c, 0)) AS cvr_z
    FROM daily d CROSS JOIN global_stats g
)
SELECT
    session_date,
    daily_sessions,
    bounce_rate_pct,
    cvr_pct,
    ROUND(GREATEST(sessions_z, bounce_z, cvr_z), 2) AS max_anomaly_score,
    CASE
        WHEN GREATEST(sessions_z, bounce_z, cvr_z) >= 3 THEN 'critical'
        WHEN GREATEST(sessions_z, bounce_z, cvr_z) >= 2 THEN 'high'
        WHEN GREATEST(sessions_z, bounce_z, cvr_z) >= 1.5 THEN 'medium'
        ELSE 'low'
    END AS severity,
    CASE
        WHEN sessions_z >= 2 AND daily_sessions > (SELECT mean_s FROM global_stats) THEN 'Traffic spike detected'
        WHEN sessions_z >= 2 AND daily_sessions < (SELECT mean_s FROM global_stats) THEN 'Traffic drop detected'
        WHEN bounce_z   >= 1.5 THEN 'Bounce rate spike detected'
        WHEN cvr_z      >= 1.5 THEN 'Conversion rate anomaly'
        ELSE 'Minor anomaly'
    END AS anomaly_description
FROM scored
WHERE GREATEST(sessions_z, bounce_z, cvr_z) >= 1.5
ORDER BY max_anomaly_score DESC;


-- 5. Recommended actions for each anomaly type
SELECT
    anomaly_type,
    trigger_condition,
    recommended_action,
    priority
FROM (VALUES
    ('Traffic Spike',    'Sessions > mean + 2 stddev',      'Check for viral content, campaign launches, or bot traffic. Scale infrastructure if needed.', 1),
    ('Traffic Drop',     'Sessions < mean - 2 stddev',      'Check server health, check for 5xx errors in server logs, verify tracking code is active.',   1),
    ('Bounce Spike',     'Bounce rate > mean + 1.5 stddev', 'Review landing page changes, page load times, and mobile responsiveness.',                     2),
    ('CVR Drop',         'CVR < mean - 1.5 stddev',         'Check checkout flow, payment gateway status, promotional offers, and form completion rates.',  1),
    ('Revenue Drop',     'Revenue < mean - 2 stddev',       'Review order values, promotional discounts, and high-value customer segments.',                 2)
) AS t(anomaly_type, trigger_condition, recommended_action, priority)
ORDER BY priority;
