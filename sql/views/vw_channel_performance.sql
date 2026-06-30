-- vw_channel_performance: channel breakdown with share % of total sessions.
CREATE OR REPLACE VIEW vw_channel_performance AS
WITH channel_totals AS (
    SELECT
        channel_grouping,
        SUM(sessions)                                                AS total_sessions,
        SUM(new_users)                                               AS total_new_users,
        SUM(pageviews)                                               AS total_pageviews,
        ROUND(AVG(session_duration_s)::numeric, 2)                   AS avg_session_duration,
        ROUND(
            100.0 * SUM(CASE WHEN bounce THEN sessions ELSE 0 END)
            / NULLIF(SUM(sessions), 0), 2
        )                                                            AS bounce_rate_pct,
        COUNT(DISTINCT session_date)                                 AS active_days
    FROM raw_ga4_sessions
    GROUP BY channel_grouping
),
grand_total AS (
    SELECT SUM(total_sessions) AS grand_sessions FROM channel_totals
)
SELECT
    c.channel_grouping,
    c.total_sessions,
    c.total_new_users,
    c.total_pageviews,
    c.avg_session_duration,
    c.bounce_rate_pct,
    c.active_days,
    ROUND(100.0 * c.total_sessions / NULLIF(g.grand_sessions, 0), 2) AS channel_share_pct
FROM channel_totals c
CROSS JOIN grand_total g
ORDER BY c.total_sessions DESC;
