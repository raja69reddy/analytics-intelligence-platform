-- Cohort Analysis Queries
-- Weekly cohorts based on channel_grouping + session_date as user proxy.
-- Note: uses session_date + channel_grouping as cohort proxy because
--       user_pseudo_id is not populated in mock data.

-- 1. Weekly cohort sizes — number of new-to-cohort sessions per week
WITH weekly AS (
    SELECT
        DATE_TRUNC('week', session_date)::DATE AS cohort_week,
        channel_grouping,
        SUM(sessions)                          AS cohort_sessions,
        SUM(new_users)                         AS new_users
    FROM raw_ga4_sessions
    GROUP BY cohort_week, channel_grouping
)
SELECT
    cohort_week,
    channel_grouping,
    cohort_sessions,
    new_users,
    ROUND(new_users::NUMERIC / NULLIF(cohort_sessions, 0) * 100, 2) AS new_user_pct
FROM weekly
ORDER BY cohort_week DESC, cohort_sessions DESC;


-- 2. Retention rate by cohort week (using session_date as proxy)
WITH all_weeks AS (
    SELECT DISTINCT DATE_TRUNC('week', session_date)::DATE AS activity_week
    FROM raw_ga4_sessions
),
cohort_base AS (
    SELECT
        DATE_TRUNC('week', session_date)::DATE AS cohort_week,
        SUM(sessions)                          AS base_sessions
    FROM raw_ga4_sessions
    GROUP BY cohort_week
),
cohort_weekly AS (
    SELECT
        DATE_TRUNC('week', session_date)::DATE AS activity_week,
        SUM(sessions)                          AS weekly_sessions
    FROM raw_ga4_sessions
    GROUP BY activity_week
)
SELECT
    b.cohort_week,
    w.activity_week,
    (w.activity_week - b.cohort_week) / 7 AS weeks_since_cohort,
    b.base_sessions,
    w.weekly_sessions,
    ROUND(w.weekly_sessions::NUMERIC / NULLIF(b.base_sessions, 0) * 100, 2) AS retention_rate_pct
FROM cohort_base b
CROSS JOIN cohort_weekly w
WHERE w.activity_week >= b.cohort_week
  AND (w.activity_week - b.cohort_week) / 7 BETWEEN 0 AND 8
ORDER BY b.cohort_week, weeks_since_cohort;


-- 3. Cohort size over time — sessions per week by cohort
SELECT
    DATE_TRUNC('week', session_date)::DATE AS cohort_week,
    SUM(sessions)                          AS total_sessions,
    SUM(new_users)                         AS new_users,
    ROUND(AVG(session_duration_s), 1)      AS avg_session_s,
    ROUND(AVG(pageviews), 2)               AS avg_pageviews
FROM raw_ga4_sessions
GROUP BY cohort_week
ORDER BY cohort_week;


-- 4. Week 1, Week 2, Week 4 retention rates per cohort
WITH cohort_base AS (
    SELECT
        DATE_TRUNC('week', session_date)::DATE AS cohort_week,
        SUM(sessions) AS base_sessions
    FROM raw_ga4_sessions
    GROUP BY cohort_week
),
weekly_activity AS (
    SELECT
        DATE_TRUNC('week', session_date)::DATE AS activity_week,
        SUM(sessions)                          AS sessions
    FROM raw_ga4_sessions
    GROUP BY activity_week
)
SELECT
    b.cohort_week,
    b.base_sessions,
    ROUND(w1.sessions::NUMERIC / NULLIF(b.base_sessions, 0) * 100, 2) AS week_1_retention_pct,
    ROUND(w2.sessions::NUMERIC / NULLIF(b.base_sessions, 0) * 100, 2) AS week_2_retention_pct,
    ROUND(w4.sessions::NUMERIC / NULLIF(b.base_sessions, 0) * 100, 2) AS week_4_retention_pct
FROM cohort_base b
LEFT JOIN weekly_activity w1 ON w1.activity_week = b.cohort_week + 7
LEFT JOIN weekly_activity w2 ON w2.activity_week = b.cohort_week + 14
LEFT JOIN weekly_activity w4 ON w4.activity_week = b.cohort_week + 28
ORDER BY b.cohort_week;


-- 5. Best and worst performing cohorts by avg session duration
WITH cohort_stats AS (
    SELECT
        DATE_TRUNC('week', session_date)::DATE AS cohort_week,
        SUM(sessions)                          AS total_sessions,
        SUM(new_users)                         AS new_users,
        ROUND(AVG(session_duration_s), 1)      AS avg_session_s,
        ROUND(SUM(bounce::INT)::NUMERIC / NULLIF(SUM(sessions), 0) * 100, 2) AS bounce_rate_pct,
        ROUND(SUM(conversions)::NUMERIC / NULLIF(SUM(sessions), 0) * 100, 2) AS cvr_pct
    FROM raw_ga4_sessions
    GROUP BY cohort_week
)
SELECT
    cohort_week,
    total_sessions,
    new_users,
    avg_session_s,
    bounce_rate_pct,
    cvr_pct,
    CASE
        WHEN RANK() OVER (ORDER BY avg_session_s DESC) <= 3 THEN 'top_3'
        WHEN RANK() OVER (ORDER BY avg_session_s ASC)  <= 3 THEN 'bottom_3'
        ELSE 'middle'
    END AS cohort_rank
FROM cohort_stats
ORDER BY avg_session_s DESC;
