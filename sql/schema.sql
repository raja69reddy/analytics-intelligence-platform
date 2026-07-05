-- ============================================================
-- Web Analytics Schema
-- All tables use CREATE TABLE IF NOT EXISTS so this file is
-- safe to re-run after the initial setup without errors.
--
-- Layers:
--   RAW       : raw_ga4_sessions, raw_server_logs, raw_scrape_pages, raw_clickstream_events
--   DIMENSION : dim_pages, dim_dates
--   FACT      : fct_sessions, fct_events
-- ============================================================


-- ─── RAW LAYER ──────────────────────────────────────────────
-- Raw tables store data exactly as it arrives from each source.
-- No transformations are applied here — ingestion scripts load
-- into these tables first, then ETL scripts promote rows to the
-- fact/dimension layer.

-- raw_ga4_sessions: one row per GA4 session exported from Google Analytics 4.
CREATE TABLE IF NOT EXISTS raw_ga4_sessions (
    id                  BIGSERIAL PRIMARY KEY,           -- auto-incrementing surrogate key
    session_date        DATE NOT NULL,                   -- calendar date the session occurred
    session_id          VARCHAR(64),                     -- GA4 session identifier (may be null for aggregated exports)
    user_pseudo_id      VARCHAR(64),                     -- GA4 pseudonymous user identifier
    user_id             VARCHAR(128),                    -- authenticated user ID if available
    country             VARCHAR(64),                     -- country from GA4 geo data
    city                VARCHAR(128),                    -- city from GA4 geo data
    device_category     VARCHAR(32),                     -- desktop | mobile | tablet
    operating_system    VARCHAR(64),                     -- Windows | macOS | iOS | Android | Linux
    browser             VARCHAR(64),                     -- Chrome | Safari | Firefox | Edge
    channel_grouping    VARCHAR(64),                     -- Organic Search | Paid Search | Direct | Referral | Social | Email
    source              VARCHAR(128),                    -- traffic source e.g. google, newsletter
    medium              VARCHAR(64),                     -- traffic medium e.g. organic, cpc, email
    campaign            VARCHAR(256),                    -- UTM campaign name, or (not set)
    landing_page        TEXT,                            -- URL of the first page in the session
    sessions            INTEGER DEFAULT 1,               -- always 1 for row-per-session format
    new_users           INTEGER DEFAULT 0,               -- 1 if this was the user's first session
    pageviews           INTEGER DEFAULT 0,               -- pages viewed during this session
    bounce              BOOLEAN DEFAULT FALSE,           -- true if session had only one pageview
    session_duration_s  NUMERIC(10,2),                   -- session length in seconds
    conversions         INTEGER DEFAULT 0,               -- goal completions during this session
    revenue             NUMERIC(12,2) DEFAULT 0,         -- revenue attributed to this session
    ingested_at         TIMESTAMPTZ DEFAULT NOW()        -- timestamp when this row was loaded
);

-- Index on session_date for date-range queries used in all dashboards
CREATE INDEX IF NOT EXISTS idx_ga4_date    ON raw_ga4_sessions(session_date);
-- Index on channel_grouping for channel-breakdown aggregations
CREATE INDEX IF NOT EXISTS idx_ga4_channel ON raw_ga4_sessions(channel_grouping);


-- raw_server_logs: one row per HTTP request parsed from web server access logs.
CREATE TABLE IF NOT EXISTS raw_server_logs (
    id              BIGSERIAL PRIMARY KEY,               -- auto-incrementing surrogate key
    log_time        TIMESTAMPTZ NOT NULL,                -- exact timestamp of the HTTP request
    ip_address      INET,                                -- client IP address (PostgreSQL INET type)
    method          VARCHAR(10),                         -- HTTP method: GET | POST | PUT | DELETE
    url             TEXT,                                -- request path e.g. /blog/post-1/
    query_string    TEXT,                                -- raw query string after '?'
    status_code     SMALLINT,                            -- HTTP response code e.g. 200 | 404 | 500
    response_bytes  INTEGER,                             -- size of HTTP response body in bytes
    referrer        TEXT,                                -- HTTP Referer header value
    user_agent      TEXT,                                -- raw User-Agent header string
    response_time_ms INTEGER,                            -- server response time in milliseconds
    ingested_at     TIMESTAMPTZ DEFAULT NOW()            -- timestamp when this row was loaded
);

-- Indexes for the three most common filter axes in log analysis
CREATE INDEX IF NOT EXISTS idx_logs_time   ON raw_server_logs(log_time);
CREATE INDEX IF NOT EXISTS idx_logs_status ON raw_server_logs(status_code);
CREATE INDEX IF NOT EXISTS idx_logs_url    ON raw_server_logs(url);


-- raw_scrape_pages: one row per page crawl, capturing SEO metadata.
CREATE TABLE IF NOT EXISTS raw_scrape_pages (
    id              BIGSERIAL PRIMARY KEY,               -- auto-incrementing surrogate key
    scraped_at      TIMESTAMPTZ NOT NULL,                -- when this page was crawled
    url             TEXT NOT NULL,                       -- full URL that was scraped
    canonical_url   TEXT,                                -- canonical URL from <link rel="canonical">
    title           TEXT,                                -- page <title> tag content
    meta_description TEXT,                               -- meta description tag content
    h1              TEXT,                                -- first <h1> heading text
    word_count      INTEGER,                             -- approximate word count of body text
    internal_links  INTEGER DEFAULT 0,                   -- count of links to the same domain
    external_links  INTEGER DEFAULT 0,                   -- count of links to other domains
    images_count    INTEGER DEFAULT 0,                   -- number of <img> elements on page
    has_schema_org  BOOLEAN DEFAULT FALSE,               -- true if page contains schema.org markup
    page_size_kb    NUMERIC(8,2),                        -- total page size in kilobytes
    load_time_ms    INTEGER,                             -- time to fully load the page in ms
    http_status     SMALLINT,                            -- HTTP status code returned by the page
    ingested_at     TIMESTAMPTZ DEFAULT NOW()            -- timestamp when this row was loaded
);

-- Indexes for joining scrape data to dim_pages by URL and querying by crawl time
CREATE INDEX IF NOT EXISTS idx_scrape_url  ON raw_scrape_pages(url);
CREATE INDEX IF NOT EXISTS idx_scrape_time ON raw_scrape_pages(scraped_at);


-- raw_clickstream_events: one row per in-browser event captured via JS tracking.
CREATE TABLE IF NOT EXISTS raw_clickstream_events (
    id              BIGSERIAL PRIMARY KEY,               -- auto-incrementing surrogate key
    event_time      TIMESTAMPTZ NOT NULL,                -- exact timestamp the event fired
    session_id      VARCHAR(64),                         -- session the event belongs to
    user_pseudo_id  VARCHAR(64),                         -- pseudonymous user identifier
    event_name      VARCHAR(128) NOT NULL,               -- click | scroll | form_submit | page_view | custom
    page_url        TEXT,                                -- URL of the page where the event fired
    element_id      VARCHAR(256),                        -- HTML id attribute of the interacted element
    element_class   VARCHAR(256),                        -- HTML class attribute of the element
    element_text    TEXT,                                -- visible text of the element (e.g. button label)
    scroll_depth_pct SMALLINT,                           -- how far user scrolled: 0-100 percent
    event_value     NUMERIC(12,2),                       -- optional numeric value e.g. revenue for purchase
    event_params    JSONB,                               -- arbitrary key-value event metadata
    device_category VARCHAR(32),                         -- desktop | mobile | tablet
    ingested_at     TIMESTAMPTZ DEFAULT NOW()            -- timestamp when this row was loaded
);

-- Indexes for the three most common clickstream query patterns
CREATE INDEX IF NOT EXISTS idx_events_time    ON raw_clickstream_events(event_time);
CREATE INDEX IF NOT EXISTS idx_events_session ON raw_clickstream_events(session_id);
CREATE INDEX IF NOT EXISTS idx_events_name    ON raw_clickstream_events(event_name);


-- ─── DIMENSION LAYER ────────────────────────────────────────
-- Dimension tables store slowly-changing descriptive attributes.
-- They are referenced by fact tables via integer foreign keys.

-- dim_pages: one row per unique URL, populated by ingestion scripts.
CREATE TABLE IF NOT EXISTS dim_pages (
    page_id         BIGSERIAL PRIMARY KEY,               -- surrogate key used in fact table FKs
    url             TEXT NOT NULL UNIQUE,                -- full URL — the natural deduplication key
    url_path        TEXT,                                -- path component e.g. /blog/post-1/
    url_domain      TEXT,                                -- domain component e.g. example.com
    page_title      TEXT,                                -- page title from scrape or server log
    page_section    VARCHAR(128),                        -- first path segment e.g. 'blog', 'products'
    is_landing_page BOOLEAN DEFAULT FALSE,               -- true if this URL appears as a GA4 landing_page
    word_count      INTEGER,                             -- word count from most recent scrape
    first_seen      DATE,                                -- first date this URL was encountered
    last_seen       DATE,                                -- most recent date this URL was encountered
    updated_at      TIMESTAMPTZ DEFAULT NOW()            -- last time this row was modified
);

-- Index on url for fast lookups during ingestion upserts
CREATE INDEX IF NOT EXISTS idx_dim_pages_url ON dim_pages(url);


-- dim_dates: one row per calendar date, pre-computed date attributes.
-- Populated by sql/populate_dates.py. Never modified after initial load.
CREATE TABLE IF NOT EXISTS dim_dates (
    date_id         INTEGER PRIMARY KEY,                 -- YYYYMMDD integer — joins cleanly with no type conversion
    full_date       DATE NOT NULL UNIQUE,                -- the actual date value
    year            SMALLINT,                            -- calendar year e.g. 2024
    quarter         SMALLINT,                            -- 1 | 2 | 3 | 4
    month           SMALLINT,                            -- 1-12
    month_name      VARCHAR(12),                         -- January | February | … | December
    week            SMALLINT,                            -- ISO 8601 week number 1-53
    day_of_week     SMALLINT,                            -- 1=Monday … 7=Sunday (ISO)
    day_name        VARCHAR(12),                         -- Monday | Tuesday | … | Sunday
    is_weekend      BOOLEAN,                             -- true for Saturday and Sunday
    is_month_start  BOOLEAN,                             -- true if day = 1
    is_month_end    BOOLEAN                              -- true if next day is in a different month
);


-- ─── FACT LAYER ─────────────────────────────────────────────
-- Fact tables store measurable events. They are narrow (IDs only for
-- dimensions) and wide (many numeric measures). All queries should
-- join fact tables to dimension tables using the integer FK columns.

-- fct_sessions: one row per processed GA4 session, linked to dimensions.
CREATE TABLE IF NOT EXISTS fct_sessions (
    session_key         BIGSERIAL PRIMARY KEY,           -- surrogate key for this fact row
    session_id          VARCHAR(64),                     -- original GA4 session ID
    user_pseudo_id      VARCHAR(64),                     -- original GA4 pseudonymous user ID
    date_id             INTEGER REFERENCES dim_dates(date_id),  -- FK to dim_dates
    page_id             INTEGER REFERENCES dim_pages(page_id),  -- FK to dim_pages (landing page)
    channel_grouping    VARCHAR(64),                     -- denormalised from raw for fast filtering
    source              VARCHAR(128),                    -- denormalised traffic source
    medium              VARCHAR(64),                     -- denormalised traffic medium
    campaign            VARCHAR(256),                    -- denormalised UTM campaign
    country             VARCHAR(64),                     -- denormalised geo country
    device_category     VARCHAR(32),                     -- denormalised device type
    is_new_user         BOOLEAN DEFAULT FALSE,           -- true if user's first ever session
    pageviews           INTEGER DEFAULT 0,               -- pages viewed in this session
    session_duration_s  NUMERIC(10,2),                   -- session length in seconds
    bounced             BOOLEAN DEFAULT FALSE,           -- true if only one pageview with no engagement
    conversions         INTEGER DEFAULT 0,               -- goal completions in this session
    revenue             NUMERIC(12,2) DEFAULT 0          -- revenue attributed to this session
);

-- Indexes for the three most common fact table filter patterns
CREATE INDEX IF NOT EXISTS idx_fct_sess_date    ON fct_sessions(date_id);
CREATE INDEX IF NOT EXISTS idx_fct_sess_channel ON fct_sessions(channel_grouping);
CREATE INDEX IF NOT EXISTS idx_fct_sess_page    ON fct_sessions(page_id);


-- fct_events: one row per processed clickstream event, linked to dimensions.
CREATE TABLE IF NOT EXISTS fct_events (
    event_key       BIGSERIAL PRIMARY KEY,               -- surrogate key for this fact row
    event_time      TIMESTAMPTZ NOT NULL,                -- exact timestamp the event fired
    date_id         INTEGER REFERENCES dim_dates(date_id),  -- FK to dim_dates
    session_id      VARCHAR(64),                         -- session this event belongs to
    user_pseudo_id  VARCHAR(64),                         -- pseudonymous user identifier
    page_id         INTEGER REFERENCES dim_pages(page_id),  -- FK to dim_pages
    event_name      VARCHAR(128),                        -- click | scroll | form_submit | purchase | etc.
    scroll_depth_pct SMALLINT,                           -- scroll position 0-100 at time of event
    event_value     NUMERIC(12,2),                       -- optional monetary or numeric value
    device_category VARCHAR(32)                          -- desktop | mobile | tablet
);

-- Indexes for the three most common event query patterns
CREATE INDEX IF NOT EXISTS idx_fct_evt_date    ON fct_events(date_id);
CREATE INDEX IF NOT EXISTS idx_fct_evt_session ON fct_events(session_id);
CREATE INDEX IF NOT EXISTS idx_fct_evt_name    ON fct_events(event_name);


-- ─── ALERTS TABLE ────────────────────────────────────────────────────────────
-- Stores resolved and active system alerts generated by the smart alerts system.
CREATE TABLE IF NOT EXISTS alerts (
    id                 BIGSERIAL PRIMARY KEY,
    alert_type         VARCHAR(64)   NOT NULL,            -- e.g. TRAFFIC_DROP, BOUNCE_SPIKE
    severity           VARCHAR(16)   NOT NULL DEFAULT 'warning', -- critical | warning | info
    message            TEXT          NOT NULL,
    recommended_action TEXT,
    is_resolved        BOOLEAN       NOT NULL DEFAULT FALSE,
    created_at         TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    resolved_at        TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_alerts_type       ON alerts(alert_type);
CREATE INDEX IF NOT EXISTS idx_alerts_severity   ON alerts(severity);
CREATE INDEX IF NOT EXISTS idx_alerts_resolved   ON alerts(is_resolved);
CREATE INDEX IF NOT EXISTS idx_alerts_created_at ON alerts(created_at DESC);
