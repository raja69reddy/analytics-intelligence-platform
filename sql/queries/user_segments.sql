-- User Segmentation Queries
-- Segments users by recency and engagement using raw_ga4_sessions.

-- 1. Segment overview: size and percentage of total unique users
WITH latest_date AS (
    SELECT MAX(session_date) AS today FROM raw_ga4_sessions
),
user_last_seen AS (
    SELECT
        user_pseudo_id,
        MAX(session_date)                   AS last_seen,
        MIN(session_date)                   AS first_seen,
        COUNT(DISTINCT session_date)        AS active_days,
        SUM(sessions)                       AS total_sessions
    FROM raw_ga4_sessions
    WHERE user_pseudo_id IS NOT NULL
    GROUP BY user_pseudo_id
),
today AS (SELECT today FROM latest_date),
segments AS (
    SELECT
        u.user_pseudo_id,
        CASE
            WHEN u.last_seen = t.today                                     THEN 'new_user'
            WHEN u.first_seen < t.today AND u.last_seen >= t.today - 1    THEN 'returning_user'
            WHEN u.active_days >= 5                                        THEN 'power_user'
            WHEN u.last_seen < t.today - 30 AND u.last_seen >= t.today - 89 THEN 'at_risk'
            WHEN u.last_seen < t.today - 90                               THEN 'lost_user'
            ELSE 'returning_user'
        END AS segment
    FROM user_last_seen u CROSS JOIN today t
)
SELECT
    segment,
    COUNT(*) AS segment_size,
    ROUND(COUNT(*)::NUMERIC / SUM(COUNT(*)) OVER () * 100, 2) AS pct_of_total
FROM segments
GROUP BY segment
ORDER BY segment_size DESC;


-- 2. New users — first visit on the most recent day of data
WITH latest_date AS (SELECT MAX(session_date) AS today FROM raw_ga4_sessions)
SELECT
    r.user_pseudo_id,
    MIN(r.session_date) AS first_seen,
    r.channel_grouping,
    r.device_category,
    r.country
FROM raw_ga4_sessions r
CROSS JOIN latest_date l
WHERE r.user_pseudo_id IS NOT NULL
GROUP BY r.user_pseudo_id, r.channel_grouping, r.device_category, r.country
HAVING MIN(r.session_date) = l.today
ORDER BY first_seen DESC
LIMIT 100;


-- 3. Returning users — visited before the latest day and active within last 2 days
WITH latest_date AS (SELECT MAX(session_date) AS today FROM raw_ga4_sessions),
user_stats AS (
    SELECT user_pseudo_id, MIN(session_date) AS first_seen, MAX(session_date) AS last_seen
    FROM raw_ga4_sessions WHERE user_pseudo_id IS NOT NULL
    GROUP BY user_pseudo_id
)
SELECT
    u.user_pseudo_id,
    u.first_seen,
    u.last_seen,
    u.last_seen - u.first_seen AS days_as_user
FROM user_stats u CROSS JOIN latest_date l
WHERE u.first_seen < l.today
  AND u.last_seen >= l.today - 1
ORDER BY u.last_seen DESC
LIMIT 100;


-- 4. Power users — 5 or more distinct active days
SELECT
    user_pseudo_id,
    COUNT(DISTINCT session_date)    AS active_days,
    SUM(sessions)                   AS total_sessions,
    SUM(pageviews)                  AS total_pageviews,
    MAX(session_date)               AS last_seen,
    MIN(session_date)               AS first_seen,
    ROUND(AVG(session_duration_s))  AS avg_session_s
FROM raw_ga4_sessions
WHERE user_pseudo_id IS NOT NULL
GROUP BY user_pseudo_id
HAVING COUNT(DISTINCT session_date) >= 5
ORDER BY active_days DESC, total_sessions DESC;


-- 5. At-risk users — no visit in 30–89 days
WITH latest_date AS (SELECT MAX(session_date) AS today FROM raw_ga4_sessions)
SELECT
    r.user_pseudo_id,
    MAX(r.session_date)             AS last_seen,
    l.today - MAX(r.session_date)   AS days_inactive,
    SUM(r.sessions)                 AS lifetime_sessions,
    r.channel_grouping
FROM raw_ga4_sessions r CROSS JOIN latest_date l
WHERE r.user_pseudo_id IS NOT NULL
GROUP BY r.user_pseudo_id, r.channel_grouping, l.today
HAVING MAX(r.session_date) < l.today - 30
   AND MAX(r.session_date) >= l.today - 89
ORDER BY days_inactive ASC
LIMIT 100;


-- 6. Lost users — no visit in 90+ days
WITH latest_date AS (SELECT MAX(session_date) AS today FROM raw_ga4_sessions)
SELECT
    r.user_pseudo_id,
    MAX(r.session_date)             AS last_seen,
    l.today - MAX(r.session_date)   AS days_inactive,
    SUM(r.sessions)                 AS lifetime_sessions,
    r.channel_grouping
FROM raw_ga4_sessions r CROSS JOIN latest_date l
WHERE r.user_pseudo_id IS NOT NULL
GROUP BY r.user_pseudo_id, r.channel_grouping, l.today
HAVING MAX(r.session_date) < l.today - 90
ORDER BY days_inactive DESC
LIMIT 100;
