-- Page Speed Analysis Queries
-- Uses raw_scrape_pages for load time metrics.

-- 1. Average page load time by page type (based on URL path depth)
SELECT
    CASE
        WHEN url ~ '^https?://[^/]+/?$'                  THEN 'homepage'
        WHEN url ~ '^https?://[^/]+/[^/]+/?$'            THEN 'top_level'
        WHEN url ~ '^https?://[^/]+/[^/]+/[^/]+/?$'      THEN 'second_level'
        ELSE 'deep'
    END AS page_type,
    COUNT(*)                               AS page_count,
    ROUND(AVG(load_time_ms), 0)           AS avg_load_ms,
    ROUND(MIN(load_time_ms), 0)           AS min_load_ms,
    ROUND(MAX(load_time_ms), 0)           AS max_load_ms,
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY load_time_ms), 0) AS median_load_ms
FROM raw_scrape_pages
WHERE http_status = 200 AND load_time_ms IS NOT NULL
GROUP BY page_type
ORDER BY avg_load_ms DESC;


-- 2. Slowest 10 pages by load time
SELECT
    DISTINCT ON (url)
    url,
    title,
    load_time_ms,
    word_count,
    page_size_kb,
    images_count,
    http_status
FROM raw_scrape_pages
WHERE http_status = 200 AND load_time_ms IS NOT NULL
ORDER BY url, load_time_ms DESC;


-- 3. Pages above 2000ms threshold
SELECT
    DISTINCT ON (url)
    url,
    load_time_ms,
    CASE
        WHEN load_time_ms > 4000 THEN 'critical (>4s)'
        WHEN load_time_ms > 3000 THEN 'poor (3-4s)'
        ELSE 'needs work (2-3s)'
    END AS severity,
    word_count,
    page_size_kb,
    images_count
FROM raw_scrape_pages
WHERE http_status = 200
  AND load_time_ms > 2000
ORDER BY url, load_time_ms DESC;


-- 4. Load time trend over time (avg per scrape date)
SELECT
    scraped_at::DATE AS scrape_date,
    COUNT(*)         AS pages_scraped,
    ROUND(AVG(load_time_ms), 0)   AS avg_load_ms,
    ROUND(MIN(load_time_ms), 0)   AS min_load_ms,
    ROUND(MAX(load_time_ms), 0)   AS max_load_ms
FROM raw_scrape_pages
WHERE http_status = 200 AND load_time_ms IS NOT NULL
GROUP BY scrape_date
ORDER BY scrape_date;


-- 5. Load time by page type based on URL content keywords
SELECT
    CASE
        WHEN url ILIKE '%blog%'       THEN 'blog'
        WHEN url ILIKE '%product%'    THEN 'product'
        WHEN url ILIKE '%category%'   THEN 'category'
        WHEN url ILIKE '%contact%'    THEN 'contact'
        WHEN url ILIKE '%about%'      THEN 'about'
        WHEN url ILIKE '%privacy%'    THEN 'legal'
        WHEN url ILIKE '%terms%'      THEN 'legal'
        ELSE 'other'
    END AS page_category,
    COUNT(*) AS pages,
    ROUND(AVG(load_time_ms), 0) AS avg_load_ms,
    ROUND(AVG(page_size_kb), 1) AS avg_size_kb,
    ROUND(AVG(images_count), 1) AS avg_images
FROM raw_scrape_pages
WHERE http_status = 200 AND load_time_ms IS NOT NULL
GROUP BY page_category
ORDER BY avg_load_ms DESC;


-- 6. Correlation between load time and bounce rate (via raw_ga4_sessions join)
SELECT
    sp.url,
    sp.load_time_ms,
    ga.bounce_rate_pct,
    CASE
        WHEN sp.load_time_ms <= 1000  THEN 'fast'
        WHEN sp.load_time_ms <= 2000  THEN 'acceptable'
        WHEN sp.load_time_ms <= 3000  THEN 'slow'
        ELSE 'very_slow'
    END AS speed_bucket
FROM (
    SELECT DISTINCT ON (url) url, load_time_ms
    FROM raw_scrape_pages
    WHERE http_status = 200 AND load_time_ms IS NOT NULL
    ORDER BY url, scraped_at DESC
) sp
JOIN (
    SELECT
        landing_page AS url,
        ROUND(SUM(bounce::INT)::NUMERIC / NULLIF(SUM(sessions), 0) * 100, 2) AS bounce_rate_pct
    FROM raw_ga4_sessions
    GROUP BY landing_page
    HAVING SUM(sessions) >= 5
) ga ON ga.url = sp.url
ORDER BY sp.load_time_ms DESC;
