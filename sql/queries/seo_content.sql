-- SEO Content Analysis Queries
-- Uses vw_seo and raw_scrape_pages.

-- 1. Top 10 pages by organic sessions
SELECT
    s.url,
    s.title,
    s.organic_sessions,
    s.organic_pageviews,
    ROUND(s.organic_bounces::NUMERIC / NULLIF(s.organic_sessions, 0) * 100, 2) AS organic_bounce_pct,
    s.avg_session_duration_s
FROM vw_seo s
ORDER BY s.organic_sessions DESC
LIMIT 10;


-- 2. Pages with word count vs avg session duration
SELECT
    s.url,
    s.word_count,
    ROUND(s.avg_session_duration_s, 1)                           AS avg_session_s,
    s.organic_sessions,
    CASE
        WHEN s.word_count >= 1500 THEN 'long_form'
        WHEN s.word_count >= 600  THEN 'medium'
        WHEN s.word_count >= 300  THEN 'short'
        ELSE 'thin'
    END AS content_length_type
FROM vw_seo s
WHERE s.word_count IS NOT NULL
ORDER BY s.word_count DESC;


-- 3. Pages missing meta descriptions
SELECT
    sp.url,
    sp.title,
    sp.word_count,
    sp.http_status,
    sp.load_time_ms
FROM raw_scrape_pages sp
WHERE (sp.meta_description IS NULL OR TRIM(sp.meta_description) = '')
  AND sp.http_status = 200
ORDER BY sp.word_count DESC NULLS LAST;


-- 4. Pages with low word count (below 300 words)
SELECT
    sp.url,
    sp.title,
    sp.word_count,
    sp.meta_description IS NOT NULL               AS has_meta,
    sp.internal_links,
    sp.external_links,
    sp.load_time_ms
FROM raw_scrape_pages sp
WHERE sp.word_count IS NOT NULL
  AND sp.word_count < 300
  AND sp.http_status = 200
ORDER BY sp.word_count ASC;


-- 5. Content freshness — days since page was last scraped
SELECT
    DISTINCT ON (sp.url)
    sp.url,
    sp.scraped_at,
    NOW()::DATE - sp.scraped_at::DATE             AS days_since_scraped,
    sp.word_count,
    sp.http_status,
    CASE
        WHEN NOW()::DATE - sp.scraped_at::DATE <= 7  THEN 'fresh'
        WHEN NOW()::DATE - sp.scraped_at::DATE <= 30 THEN 'recent'
        WHEN NOW()::DATE - sp.scraped_at::DATE <= 90 THEN 'aging'
        ELSE 'stale'
    END AS freshness
FROM raw_scrape_pages sp
ORDER BY sp.url, sp.scraped_at DESC;


-- 6. Internal link count per page
SELECT
    DISTINCT ON (url)
    url,
    internal_links,
    CASE
        WHEN internal_links = 0         THEN 'orphan'
        WHEN internal_links BETWEEN 1 AND 5  THEN 'low'
        WHEN internal_links BETWEEN 6 AND 20 THEN 'good'
        ELSE 'rich'
    END AS internal_link_grade
FROM raw_scrape_pages
WHERE http_status = 200
ORDER BY url, scraped_at DESC;


-- 7. External link count per page
SELECT
    DISTINCT ON (url)
    url,
    external_links,
    CASE
        WHEN external_links = 0         THEN 'none'
        WHEN external_links BETWEEN 1 AND 5  THEN 'few'
        WHEN external_links BETWEEN 6 AND 15 THEN 'moderate'
        ELSE 'many'
    END AS external_link_grade
FROM raw_scrape_pages
WHERE http_status = 200
ORDER BY url, scraped_at DESC;


-- 8. Content score combining word count, meta, and links (0–100)
WITH latest AS (
    SELECT DISTINCT ON (url)
        url, title, meta_description, word_count,
        internal_links, external_links, load_time_ms
    FROM raw_scrape_pages
    WHERE http_status = 200
    ORDER BY url, scraped_at DESC
)
SELECT
    url,
    title,
    word_count,
    meta_description IS NOT NULL AND TRIM(meta_description) <> ''    AS has_meta,
    internal_links,
    external_links,
    load_time_ms,
    -- Score breakdown (max 100)
    LEAST(ROUND(word_count::NUMERIC / 1500 * 40, 0), 40)            AS word_score,   -- 0-40 pts
    CASE WHEN meta_description IS NOT NULL AND TRIM(meta_description) <> ''
         THEN 20 ELSE 0 END                                          AS meta_score,   -- 0 or 20 pts
    LEAST(ROUND(internal_links::NUMERIC / 10 * 20, 0), 20)         AS links_score,  -- 0-20 pts
    CASE WHEN load_time_ms <= 1000 THEN 20
         WHEN load_time_ms <= 2000 THEN 10
         ELSE 0 END                                                  AS speed_score,  -- 0-20 pts
    -- Total content score
    LEAST(ROUND(word_count::NUMERIC / 1500 * 40, 0), 40)
        + CASE WHEN meta_description IS NOT NULL AND TRIM(meta_description) <> '' THEN 20 ELSE 0 END
        + LEAST(ROUND(internal_links::NUMERIC / 10 * 20, 0), 20)
        + CASE WHEN load_time_ms <= 1000 THEN 20
               WHEN load_time_ms <= 2000 THEN 10
               ELSE 0 END                                            AS content_score
FROM latest
ORDER BY content_score DESC;
