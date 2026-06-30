-- Performance indexes for all raw tables.
-- CREATE INDEX IF NOT EXISTS used so this script is safe to re-run.

-- raw_ga4_sessions
CREATE INDEX IF NOT EXISTS idx_ga4_session_date
    ON raw_ga4_sessions (session_date);

CREATE INDEX IF NOT EXISTS idx_ga4_channel
    ON raw_ga4_sessions (channel_grouping);

-- raw_server_logs
CREATE INDEX IF NOT EXISTS idx_server_logs_log_time
    ON raw_server_logs (log_time);

CREATE INDEX IF NOT EXISTS idx_server_logs_url
    ON raw_server_logs (url);

CREATE INDEX IF NOT EXISTS idx_server_logs_status
    ON raw_server_logs (status_code);

-- raw_clickstream_events
CREATE INDEX IF NOT EXISTS idx_clickstream_event_time
    ON raw_clickstream_events (event_time);

CREATE INDEX IF NOT EXISTS idx_clickstream_event_name
    ON raw_clickstream_events (event_name);

CREATE INDEX IF NOT EXISTS idx_clickstream_page_url
    ON raw_clickstream_events (page_url);

-- raw_scrape_pages
CREATE INDEX IF NOT EXISTS idx_scrape_pages_url
    ON raw_scrape_pages (url);
