-- Keyword & Content Analysis Queries
-- Uses raw_scrape_pages for title, meta, and content analysis.

-- 1. Most common words in page titles
-- Split title into words and count frequency
WITH title_words AS (
    SELECT
        LOWER(TRIM(REGEXP_REPLACE(word, '[^a-zA-Z]', '', 'g'))) AS word
    FROM raw_scrape_pages,
         UNNEST(STRING_TO_ARRAY(title, ' ')) AS word
    WHERE title IS NOT NULL
      AND http_status = 200
      AND LENGTH(TRIM(word)) > 3
),
stopwords AS (
    SELECT word FROM (VALUES ('with'),('that'),('from'),('this'),('have'),('your'),('will'),
                             ('been'),('they'),('were'),('when'),('what'),('about'),('into'),
                             ('more'),('than'),('also'),('some'),('which')) sw(word)
)
SELECT
    tw.word,
    COUNT(*) AS frequency
FROM title_words tw
WHERE tw.word NOT IN (SELECT word FROM stopwords)
  AND LENGTH(tw.word) > 3
GROUP BY tw.word
ORDER BY frequency DESC
LIMIT 20;


-- 2. Most common words in meta descriptions
WITH meta_words AS (
    SELECT
        LOWER(TRIM(REGEXP_REPLACE(word, '[^a-zA-Z]', '', 'g'))) AS word
    FROM raw_scrape_pages,
         UNNEST(STRING_TO_ARRAY(meta_description, ' ')) AS word
    WHERE meta_description IS NOT NULL
      AND http_status = 200
),
stopwords AS (
    SELECT word FROM (VALUES ('with'),('that'),('from'),('this'),('have'),('your'),('will'),
                             ('been'),('they'),('were'),('when'),('what'),('about'),('into'),
                             ('more'),('than'),('also'),('some'),('which'),('and'),('the'),
                             ('for'),('are'),('our')) sw(word)
)
SELECT
    mw.word,
    COUNT(*) AS frequency
FROM meta_words mw
WHERE mw.word NOT IN (SELECT word FROM stopwords)
  AND LENGTH(mw.word) > 3
GROUP BY mw.word
ORDER BY frequency DESC
LIMIT 20;


-- 3. Pages grouped by content topic (based on URL path segment)
SELECT
    SPLIT_PART(REPLACE(url, 'https://', ''), '/', 2)  AS topic_category,
    COUNT(DISTINCT url)                                AS page_count,
    ROUND(AVG(word_count), 0)                         AS avg_word_count,
    ROUND(AVG(load_time_ms), 0)                       AS avg_load_ms,
    COUNT(CASE WHEN meta_description IS NOT NULL THEN 1 END) AS pages_with_meta
FROM raw_scrape_pages
WHERE http_status = 200
GROUP BY topic_category
ORDER BY page_count DESC;


-- 4. Title length distribution
SELECT
    CASE
        WHEN LENGTH(title) <= 30  THEN 'short (<= 30 chars)'
        WHEN LENGTH(title) <= 60  THEN 'optimal (31-60 chars)'
        WHEN LENGTH(title) <= 80  THEN 'long (61-80 chars)'
        ELSE 'too long (> 80 chars)'
    END AS length_bucket,
    COUNT(*) AS page_count,
    ROUND(AVG(LENGTH(title)), 1) AS avg_title_length,
    MIN(LENGTH(title)) AS min_length,
    MAX(LENGTH(title)) AS max_length
FROM raw_scrape_pages
WHERE title IS NOT NULL AND http_status = 200
GROUP BY length_bucket
ORDER BY MIN(LENGTH(title));


-- 5. Meta description length distribution
SELECT
    CASE
        WHEN meta_description IS NULL OR TRIM(meta_description) = '' THEN 'missing'
        WHEN LENGTH(meta_description) <= 70   THEN 'too short (<= 70 chars)'
        WHEN LENGTH(meta_description) <= 160  THEN 'optimal (71-160 chars)'
        WHEN LENGTH(meta_description) <= 200  THEN 'long (161-200 chars)'
        ELSE 'too long (> 200 chars)'
    END AS length_bucket,
    COUNT(*) AS page_count,
    ROUND(AVG(LENGTH(meta_description)), 1) AS avg_meta_length
FROM raw_scrape_pages
WHERE http_status = 200
GROUP BY length_bucket
ORDER BY page_count DESC;


-- 6. Pages with duplicate titles
SELECT
    LOWER(TRIM(title))    AS normalized_title,
    COUNT(*) AS duplicate_count,
    ARRAY_AGG(url)        AS urls
FROM raw_scrape_pages
WHERE title IS NOT NULL AND http_status = 200
GROUP BY normalized_title
HAVING COUNT(*) > 1
ORDER BY duplicate_count DESC;


-- 7. Pages with duplicate meta descriptions
SELECT
    LEFT(LOWER(TRIM(meta_description)), 100) AS meta_snippet,
    COUNT(*)                                  AS duplicate_count,
    ARRAY_AGG(url)                            AS urls
FROM raw_scrape_pages
WHERE meta_description IS NOT NULL
  AND TRIM(meta_description) <> ''
  AND http_status = 200
GROUP BY meta_snippet
HAVING COUNT(*) > 1
ORDER BY duplicate_count DESC;
