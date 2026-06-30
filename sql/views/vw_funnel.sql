DROP VIEW IF EXISTS vw_funnel CASCADE;
-- vw_funnel: staged conversion funnel from raw_ga4_sessions.
-- Each stage is a strict subset of the previous to ensure monotone decreasing counts.
-- Stage 1: All sessions
-- Stage 2: Sessions lasting > 10s (entry intent)
-- Stage 3: Sessions with 2+ pageviews (exploration)
-- Stage 4: Sessions with 3+ pageviews AND duration > 60s (engaged)
-- Stage 5: Sessions with 4+ pageviews AND duration > 120s AND not bounce (conversion intent)
CREATE OR REPLACE VIEW vw_funnel AS
WITH totals AS (
    SELECT
        SUM(sessions)                                                                     AS step1_all,
        SUM(CASE WHEN session_duration_s > 10
                 THEN sessions ELSE 0 END)                                                AS step2_entry,
        SUM(CASE WHEN pageviews >= 2 AND session_duration_s > 10
                 THEN sessions ELSE 0 END)                                                AS step3_explore,
        SUM(CASE WHEN pageviews >= 3 AND session_duration_s > 60
                 THEN sessions ELSE 0 END)                                                AS step4_engaged,
        SUM(CASE WHEN pageviews >= 4 AND session_duration_s > 120 AND bounce = FALSE
                 THEN sessions ELSE 0 END)                                                AS step5_converted
    FROM raw_ga4_sessions
),
stages AS (
    SELECT 1 AS stage_order, 'All Sessions'  AS stage_name, step1_all      AS users_reached FROM totals
    UNION ALL
    SELECT 2, 'Entry Intent',  step2_entry   FROM totals
    UNION ALL
    SELECT 3, 'Exploration',   step3_explore FROM totals
    UNION ALL
    SELECT 4, 'Engaged',       step4_engaged FROM totals
    UNION ALL
    SELECT 5, 'Converted',     step5_converted FROM totals
)
SELECT
    stage_order,
    stage_name,
    users_reached,
    COALESCE(
        users_reached - LEAD(users_reached) OVER (ORDER BY stage_order), 0
    )                                                                                     AS drop_off_count,
    ROUND(
        100.0 * COALESCE(
            users_reached - LEAD(users_reached) OVER (ORDER BY stage_order), 0
        ) / NULLIF(users_reached, 0), 2
    )                                                                                     AS drop_off_pct,
    ROUND(
        100.0 * users_reached
        / NULLIF(FIRST_VALUE(users_reached) OVER (ORDER BY stage_order), 0), 2
    )                                                                                     AS completion_rate_pct
FROM stages
ORDER BY stage_order;
