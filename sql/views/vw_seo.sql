-- ============================================================
-- vw_seo
-- Purpose : SEO and content performance for organic search traffic,
--           enriched with the latest scraped page metadata.
-- Sources : fct_sessions JOIN dim_dates JOIN dim_pages
--           LEFT JOIN LATERAL raw_scrape_pages (most recent scrape)
--           LEFT JOIN fct_events (scroll events)
-- Filter  : channel_grouping = 'Organic Search' only
-- Key metrics:
--   organic_sessions      — sessions arriving via organic search
--   organic_pageviews     — pageviews from organic sessions
--   avg_time_on_page_s    — mean session duration for organic visitors
--   organic_bounce_rate_pct— bounce rate for organic traffic
--   organic_conversions   — conversions from organic sessions
--   avg_scroll_depth_pct  — scroll engagement of organic visitors
--   word_count            — content length from latest scrape
-- Usage : SELECT * FROM vw_seo ORDER BY organic_sessions DESC
-- ============================================================
CREATE OR REPLACE VIEW vw_seo AS
SELECT
    d.full_date,
    p.url,
    p.url_path,
    p.page_title,
    sp.meta_description,
    sp.word_count,
    sp.internal_links,
    sp.external_links,
    sp.has_schema_org,
    sp.load_time_ms,
    -- organic traffic metrics
    COUNT(DISTINCT s.session_id)                AS organic_sessions,
    SUM(s.pageviews)                            AS organic_pageviews,
    ROUND(AVG(s.session_duration_s), 2)         AS avg_time_on_page_s,
    SUM(CASE WHEN s.bounced THEN 1 ELSE 0 END)  AS organic_bounces,
    ROUND(
        100.0 * SUM(CASE WHEN s.bounced THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2
    )                                           AS organic_bounce_rate_pct,
    SUM(s.conversions)                          AS organic_conversions,
    -- scroll engagement from organic visitors
    ROUND(
        AVG(e.avg_scroll_pct), 2
    )                                           AS avg_scroll_depth_pct
FROM fct_sessions s
JOIN dim_dates d  ON s.date_id = d.date_id
JOIN dim_pages p  ON s.page_id = p.page_id
-- pull latest scrape metadata for this URL
LEFT JOIN LATERAL (
    SELECT meta_description, word_count, internal_links, external_links,
           has_schema_org, load_time_ms
    FROM raw_scrape_pages rsp
    WHERE rsp.url = p.url
    ORDER BY rsp.scraped_at DESC
    LIMIT 1
) sp ON TRUE
LEFT JOIN (
    SELECT page_id, AVG(scroll_depth_pct) AS avg_scroll_pct
    FROM fct_events
    WHERE event_name = 'scroll'
    GROUP BY page_id
) e ON e.page_id = s.page_id
WHERE s.channel_grouping = 'Organic Search'
GROUP BY 1,2,3,4,5,6,7,8,9,10;
