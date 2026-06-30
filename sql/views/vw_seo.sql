-- vw_seo: page-level SEO content metrics sourced from raw_scrape_pages and raw_ga4_sessions.
-- Shows word count per page, missing meta descriptions, content length distribution,
-- and organic traffic from GA4.
CREATE OR REPLACE VIEW vw_seo AS
WITH scrape_latest AS (
    -- Use the most recent scrape for each URL
    SELECT DISTINCT ON (url)
        url,
        scraped_at,
        title,
        meta_description,
        word_count
    FROM raw_scrape_pages
    ORDER BY url, scraped_at DESC
),
content_bands AS (
    -- Content length distribution buckets
    SELECT
        url,
        word_count,
        CASE
            WHEN word_count < 300  THEN 'thin (<300)'
            WHEN word_count < 700  THEN 'short (300-699)'
            WHEN word_count < 1500 THEN 'medium (700-1499)'
            ELSE                        'long (1500+)'
        END AS content_length_band
    FROM scrape_latest
),
ga4_organic AS (
    -- Organic sessions per landing page from raw GA4 data
    SELECT
        landing_page,
        COUNT(*) AS organic_sessions,
        SUM(pageviews) AS organic_pageviews,
        ROUND(AVG(session_duration_s)::numeric, 2) AS avg_session_duration_s,
        SUM(CASE WHEN bounce THEN 1 ELSE 0 END) AS organic_bounces
    FROM raw_ga4_sessions
    WHERE channel_grouping = 'Organic Search'
      AND landing_page IS NOT NULL
    GROUP BY landing_page
)
SELECT
    s.url,
    s.scraped_at,
    s.title,
    s.meta_description,
    CASE WHEN s.meta_description IS NULL OR s.meta_description = ''
         THEN TRUE ELSE FALSE END                   AS missing_meta_description,
    s.word_count,
    c.content_length_band,
    COALESCE(g.organic_sessions,      0)            AS organic_sessions,
    COALESCE(g.organic_pageviews,     0)            AS organic_pageviews,
    COALESCE(g.avg_session_duration_s, 0)           AS avg_session_duration_s,
    COALESCE(g.organic_bounces,        0)           AS organic_bounces
FROM scrape_latest s
JOIN content_bands c ON c.url = s.url
LEFT JOIN ga4_organic g ON g.landing_page = s.url
ORDER BY s.word_count DESC;
