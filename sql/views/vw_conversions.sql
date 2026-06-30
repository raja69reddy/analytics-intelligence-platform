-- ============================================================
-- vw_conversions
-- Purpose : Conversion and revenue metrics broken down by traffic source,
--           campaign, and device. Drives the Conversions dashboard page.
-- Sources : fct_sessions JOIN dim_dates
-- Key metrics:
--   sessions              — total sessions for this segment
--   conversions           — count of sessions with at least one conversion
--   revenue               — total revenue across all sessions
--   conversion_rate_pct   — converting sessions / total sessions * 100
--   revenue_per_conversion— average order value (revenue / conversions)
-- Usage : SELECT * FROM vw_conversions WHERE channel_grouping = 'Paid Search'
-- ============================================================
CREATE OR REPLACE VIEW vw_conversions AS
SELECT
    d.full_date,
    s.channel_grouping,
    s.source,
    s.medium,
    s.campaign,
    s.device_category,
    COUNT(*)                    AS sessions,
    SUM(s.conversions)          AS conversions,
    SUM(s.revenue)              AS revenue,
    ROUND(
        100.0 * SUM(CASE WHEN s.conversions > 0 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 4
    )                           AS conversion_rate_pct,
    ROUND(
        SUM(s.revenue) / NULLIF(SUM(s.conversions), 0), 2
    )                           AS revenue_per_conversion
FROM fct_sessions s
JOIN dim_dates d ON s.date_id = d.date_id
GROUP BY 1,2,3,4,5,6;


CREATE OR REPLACE VIEW vw_goal_completions AS
SELECT
    d.full_date,
    e.event_name                AS goal_type,
    s.channel_grouping,
    s.source,
    s.medium,
    COUNT(*)                    AS completions,
    ROUND(AVG(e.event_value), 2) AS avg_event_value
FROM fct_events e
JOIN dim_dates d  ON e.date_id = d.date_id
JOIN fct_sessions s ON e.session_id = s.session_id AND e.date_id = s.date_id
WHERE e.event_name IN ('form_submit', 'purchase', 'signup', 'download', 'contact')
GROUP BY 1,2,3,4,5;
