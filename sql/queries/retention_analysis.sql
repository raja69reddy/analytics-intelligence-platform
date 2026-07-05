-- Retention Analysis Queries
-- Uses raw_ga4_sessions. Note: user_pseudo_id/session_id are NULL in mock data,
-- so these queries use date-based approximations for user counts.

-- 1. Daily Active Users (DAU) — unique session_dates with activity
SELECT
    session_date,
    SUM(sessions)       AS daily_sessions,
    SUM(new_users)      AS new_users,
    SUM(sessions) - SUM(new_users) AS returning_users
FROM raw_ga4_sessions
GROUP BY session_date
ORDER BY session_date;


-- 2. Weekly Active Users (WAU)
SELECT
    DATE_TRUNC('week', session_date)::DATE AS week_start,
    SUM(sessions)  AS weekly_sessions,
    SUM(new_users) AS weekly_new_users,
    COUNT(DISTINCT session_date) AS active_days_in_week
FROM raw_ga4_sessions
GROUP BY week_start
ORDER BY week_start;


-- 3. Monthly Active Users (MAU)
SELECT
    DATE_TRUNC('month', session_date)::DATE AS month_start,
    SUM(sessions)  AS monthly_sessions,
    SUM(new_users) AS monthly_new_users,
    COUNT(DISTINCT session_date) AS active_days_in_month
FROM raw_ga4_sessions
GROUP BY month_start
ORDER BY month_start;


-- 4. DAU/MAU ratio — stickiness score
WITH dau AS (
    SELECT session_date, SUM(sessions) AS daily_sessions
    FROM raw_ga4_sessions GROUP BY session_date
),
mau AS (
    SELECT
        DATE_TRUNC('month', session_date)::DATE AS month_start,
        SUM(sessions) AS monthly_sessions,
        COUNT(DISTINCT session_date) AS active_days
    FROM raw_ga4_sessions GROUP BY month_start
)
SELECT
    m.month_start,
    m.monthly_sessions,
    m.active_days,
    ROUND(m.monthly_sessions::NUMERIC / NULLIF(m.active_days, 0), 1) AS avg_dau,
    ROUND(
        (m.monthly_sessions::NUMERIC / NULLIF(m.active_days, 0))
        / NULLIF(m.monthly_sessions, 0) * 100, 2
    ) AS dau_mau_ratio_pct
FROM mau m
ORDER BY m.month_start;


-- 5. User retention rate by week — returning users as % of prior week users
WITH weekly AS (
    SELECT
        DATE_TRUNC('week', session_date)::DATE AS week_start,
        SUM(sessions)  AS weekly_sessions,
        SUM(new_users) AS new_users
    FROM raw_ga4_sessions
    GROUP BY week_start
)
SELECT
    week_start,
    weekly_sessions,
    new_users,
    weekly_sessions - new_users AS returning_users,
    ROUND((weekly_sessions - new_users)::NUMERIC / NULLIF(weekly_sessions, 0) * 100, 2) AS retention_rate_pct,
    LAG(weekly_sessions) OVER (ORDER BY week_start) AS prev_week_sessions,
    ROUND(
        (weekly_sessions::NUMERIC / NULLIF(LAG(weekly_sessions) OVER (ORDER BY week_start), 0) - 1) * 100
    , 2) AS wow_growth_pct
FROM weekly
ORDER BY week_start;


-- 6. Churn rate — sessions from users who haven't visited in 30+ days
-- Approximated as: sessions where the session is 30+ days before latest date
WITH latest AS (SELECT MAX(session_date) AS today FROM raw_ga4_sessions),
monthly AS (
    SELECT
        DATE_TRUNC('month', session_date)::DATE AS month_start,
        SUM(sessions) AS sessions
    FROM raw_ga4_sessions, latest
    WHERE session_date < today - 29
    GROUP BY month_start
)
SELECT
    month_start,
    sessions AS potentially_churned_sessions,
    ROUND(sessions::NUMERIC / (SELECT SUM(sessions) FROM raw_ga4_sessions) * 100, 2) AS churn_proxy_pct
FROM monthly
ORDER BY month_start;


-- 7. Re-engagement rate — sessions on pages previously visited (returning user pct by channel)
SELECT
    channel_grouping,
    SUM(sessions)   AS total_sessions,
    SUM(new_users)  AS new_users,
    SUM(sessions) - SUM(new_users) AS returning_sessions,
    ROUND((SUM(sessions) - SUM(new_users))::NUMERIC / NULLIF(SUM(sessions), 0) * 100, 2) AS re_engagement_rate_pct
FROM raw_ga4_sessions
GROUP BY channel_grouping
ORDER BY re_engagement_rate_pct DESC;
