# Data Dictionary — Analytics Intelligence Platform

This document describes every table, view, column, and AI feature in the platform.

---

## Raw Tables

### `raw_ga4_sessions`
One row per GA4 session exported from Google Analytics 4. The primary traffic source of truth.

| Column | Type | Description |
|--------|------|-------------|
| id | BIGSERIAL | Surrogate primary key |
| session_date | DATE | Calendar date of the session |
| session_id | VARCHAR(64) | GA4 session identifier (NULL in mock data) |
| user_pseudo_id | VARCHAR(64) | Pseudonymous user identifier (NULL in mock data) |
| user_id | VARCHAR(64) | Authenticated user ID if available |
| country | VARCHAR(64) | Country of the session (ISO name) |
| city | VARCHAR(128) | City of the session |
| device_category | VARCHAR(32) | `desktop`, `mobile`, or `tablet` |
| operating_system | VARCHAR(64) | User OS (Windows, Android, iOS, etc.) |
| browser | VARCHAR(64) | User browser (Chrome, Safari, etc.) |
| channel_grouping | VARCHAR(64) | Traffic channel: Organic, Direct, Email, Social, Paid, Referral |
| source | VARCHAR(128) | Traffic source (google, newsletter, etc.) |
| medium | VARCHAR(64) | Traffic medium (organic, cpc, email, etc.) |
| campaign | VARCHAR(256) | UTM campaign name if present |
| landing_page | TEXT | First page URL of the session |
| sessions | INTEGER | Number of sessions in this aggregate row |
| new_users | INTEGER | New users count within these sessions |
| pageviews | INTEGER | Total pageviews across these sessions |
| bounce | BOOLEAN | `TRUE` if the session had only one interaction |
| session_duration_s | NUMERIC(10,2) | Average session duration in seconds |
| conversions | INTEGER | Goal completion count (0 in mock data) |
| revenue | NUMERIC(12,2) | Revenue generated (0 in mock data) |
| ingested_at | TIMESTAMPTZ | Timestamp when this row was ingested |

---

### `raw_server_logs`
One row per HTTP request logged by the web server. Used for page-level performance analysis.

| Column | Type | Description |
|--------|------|-------------|
| id | BIGSERIAL | Surrogate primary key |
| log_time | TIMESTAMPTZ | Exact timestamp of the HTTP request |
| ip_address | VARCHAR(45) | Client IP address (IPv4 or IPv6) |
| method | VARCHAR(10) | HTTP method: GET, POST, etc. |
| url | TEXT | Request URL path (no host) |
| query_string | TEXT | Query parameters appended to the URL |
| status_code | SMALLINT | HTTP response code (200, 301, 404, 500, etc.) |
| response_bytes | INTEGER | Response body size in bytes |
| referrer | TEXT | HTTP Referer header if present |
| user_agent | TEXT | Full User-Agent string |
| response_time_ms | INTEGER | Server response time in milliseconds |
| ingested_at | TIMESTAMPTZ | Timestamp when this row was ingested |

---

### `raw_clickstream_events`
One row per client-side event (click, scroll, pageview, form submit) from the JS tracking snippet.

| Column | Type | Description |
|--------|------|-------------|
| id | BIGSERIAL | Surrogate primary key |
| event_time | TIMESTAMPTZ | Exact timestamp the event fired on the client |
| session_id | VARCHAR(64) | Session the event belongs to (NULL in mock data) |
| user_pseudo_id | VARCHAR(64) | Pseudonymous user identifier (NULL in mock data) |
| event_name | VARCHAR(128) | Event type: `click`, `scroll`, `pageview`, `form_submit`, `purchase` |
| page_url | TEXT | URL of the page where the event fired |
| element_id | VARCHAR(128) | DOM element id that triggered the event |
| element_class | VARCHAR(256) | CSS classes of the triggering element |
| element_text | TEXT | Visible text of the triggering element (truncated) |
| scroll_depth_pct | SMALLINT | Scroll position 0–100 at the time of a scroll event |
| event_value | NUMERIC(12,2) | Optional monetary or numeric value (e.g., purchase amount) |
| event_params | JSONB | Arbitrary key-value pairs for custom event parameters |
| device_category | VARCHAR(32) | `desktop`, `mobile`, or `tablet` |
| ingested_at | TIMESTAMPTZ | Timestamp when this row was ingested |

---

### `raw_scrape_pages`
One row per page URL crawled by the SEO scraper. Updated on each scrape run.

| Column | Type | Description |
|--------|------|-------------|
| id | BIGSERIAL | Surrogate primary key |
| scraped_at | TIMESTAMPTZ | Timestamp when this page was scraped |
| url | TEXT | Page URL (unique per scrape run) |
| canonical_url | TEXT | Canonical URL from `<link rel="canonical">` |
| title | VARCHAR(512) | `<title>` tag content |
| meta_description | TEXT | `<meta name="description">` content |
| h1 | TEXT | First `<h1>` tag content |
| word_count | INTEGER | Approximate word count of visible body text |
| internal_links | INTEGER | Count of internal `<a href>` links on the page |
| external_links | INTEGER | Count of external `<a href>` links on the page |
| images_count | INTEGER | Count of `<img>` tags |
| has_schema_org | BOOLEAN | `TRUE` if structured data (schema.org) is present |
| page_size_kb | NUMERIC(10,2) | Raw HTML size in kilobytes |
| load_time_ms | INTEGER | Full page load time measured by the scraper |
| http_status | SMALLINT | HTTP status code returned by the page |
| ingested_at | TIMESTAMPTZ | Timestamp when this row was ingested |

---

## Dimension Tables

### `dim_pages`
Deduplicated page URL dimension. Populated from server logs.

| Column | Type | Description |
|--------|------|-------------|
| page_id | SERIAL | Surrogate primary key |
| url | TEXT | Normalised page URL (unique) |
| page_section | VARCHAR(128) | Top-level section derived from URL path |
| page_title | VARCHAR(512) | Page title from scrape data (may be NULL) |

### `dim_dates`
Date dimension spanning 2023-01-01 to 2025-12-31 (1,096 rows). Pre-populated via `sql/populate_dates.py`.

| Column | Type | Description |
|--------|------|-------------|
| date_id | INTEGER | Compact date key in YYYYMMDD format |
| full_date | DATE | Calendar date |
| year | SMALLINT | 4-digit year |
| quarter | SMALLINT | Quarter 1–4 |
| month | SMALLINT | Month 1–12 |
| month_name | VARCHAR(12) | Full month name (January, etc.) |
| week | SMALLINT | ISO week number |
| day_of_week | SMALLINT | Day of week 1 (Mon) – 7 (Sun) |
| day_name | VARCHAR(12) | Full day name (Monday, etc.) |
| is_weekend | BOOLEAN | `TRUE` for Saturday and Sunday |
| is_month_start | BOOLEAN | `TRUE` on the first day of the month |
| is_month_end | BOOLEAN | `TRUE` on the last day of the month |

---

## Alerts Table

### `alerts`
Stores active and resolved system alerts generated by the smart alerts engine.

| Column | Type | Description |
|--------|------|-------------|
| id | BIGSERIAL | Surrogate primary key |
| alert_type | VARCHAR(64) | Alert rule name: TRAFFIC_DROP, BOUNCE_SPIKE, etc. |
| severity | VARCHAR(16) | `critical`, `warning`, or `info` |
| message | TEXT | Human-readable alert description |
| recommended_action | TEXT | Suggested remediation step |
| is_resolved | BOOLEAN | `FALSE` (active) or `TRUE` (resolved) |
| created_at | TIMESTAMPTZ | When the alert was raised |
| resolved_at | TIMESTAMPTZ | When the alert was marked resolved (NULL if active) |

---

## SQL Views

| View | Description |
|------|-------------|
| `vw_daily_traffic` | Daily sessions, new users, pageviews, bounce rate, 7-day rolling avg |
| `vw_channel_performance` | Per-channel sessions, bounce rate, avg duration, share % |
| `vw_new_vs_returning` | Daily split of new vs returning user sessions |
| `vw_conversions` | Daily conversion rate and revenue by channel/source/medium |
| `vw_goal_completions` | Goal events by type, channel, date (from fct_sessions) |
| `vw_top_pages` | Top pages by server log requests, error rate, avg response time |
| `vw_page_performance` | Per-page response time, error rate, last-visited |
| `vw_behavior` | Clickstream-based per-page engagement (scroll depth, events, response time) |
| `vw_scroll_depth` | Per-page scroll depth buckets (0–25%, 25–50%, 50–75%, 75–100%) |
| `vw_engagement_events` | Per-page event counts broken down by type (click/scroll/pageview/form_submit) |
| `vw_seo` | SEO-enriched page view joined with scrape data (word count, meta, load time) |
| `vw_traffic` | High-level traffic summary (total sessions, users, pageviews, revenue) |
| `vw_traffic_by_hour` | Server log request count grouped by hour of day |
| `vw_device_breakdown` | Sessions, bounce rate, duration by device category |
| `vw_geo_performance` | Sessions and engagement by country/city |
| `vw_funnel` | Homepage → Product → Cart → Checkout → Purchase funnel counts |
| `vw_error_pages` | Pages with the highest error (4xx/5xx) rates |
| `vw_user_agents` | Top browser/OS combinations by request count |

---

## AI Features

| Feature | Module | Description |
|---------|--------|-------------|
| Anomaly Detection | `ai/anomaly_detection/` | IsolationForest model detects traffic anomalies. Results saved to `data/processed/anomalies.csv`. Anomaly scores mapped to severity (high/medium/low). |
| Natural Language Query | `ai/nlq/` | GPT-3.5-turbo converts plain-English questions into SQL queries, executes them, and returns tabular results. |
| AI Report Generation | `ai/report_generator/` | GPT-3.5-turbo auto-generates markdown insight summaries from dashboard data. |
| Traffic Forecasting | `ai/forecasting/traffic_forecaster.py` | Facebook Prophet model forecasts next 7–60 days of session volume. Uses additive seasonality. Model stored at `ai/models/traffic_forecast_model.pkl`. |
| Conversion Forecasting | `ai/forecasting/conversion_forecaster.py` | Facebook Prophet model forecasts daily CVR %. Clips output to 0–100%. Model stored at `ai/models/conversion_forecast_model.pkl`. |
| Smart Alerts | `utils/alerts.py`, `utils/alert_rules.py` | Rule-based alert system with 7 checks (traffic drop, bounce spike, CVR drop, page speed degradation, AI anomaly, data staleness, error rate). Results aggregated in `generate_alert_summary()`. |

---

## Sample Queries

### Traffic — sessions by channel for the last 30 days
```sql
SELECT channel_grouping,
       SUM(sessions) AS total_sessions,
       ROUND(SUM(bounce::INT)::NUMERIC / NULLIF(SUM(sessions), 0) * 100, 2) AS bounce_pct
FROM raw_ga4_sessions
WHERE session_date >= CURRENT_DATE - 30
GROUP BY channel_grouping
ORDER BY total_sessions DESC;
```

### Behavior — top 10 pages by engagement score
```sql
WITH m AS (
    SELECT landing_page, COUNT(*) n,
           ROUND(AVG(session_duration_s), 1) d,
           ROUND(AVG(pageviews), 2) pv,
           ROUND(SUM(bounce::INT)::NUMERIC / NULLIF(COUNT(*), 0) * 100, 2) br
    FROM raw_ga4_sessions GROUP BY landing_page HAVING COUNT(*) >= 10
)
SELECT landing_page,
       ROUND(LEAST(d/300.0,1)*40 + LEAST((pv-1)/4.0,1)*30 + (1-br/100.0)*30, 2) AS engagement_score
FROM m ORDER BY engagement_score DESC LIMIT 10;
```

### SEO — pages missing meta descriptions
```sql
SELECT url, title, word_count, load_time_ms
FROM raw_scrape_pages
WHERE (meta_description IS NULL OR meta_description = '')
  AND http_status = 200
ORDER BY word_count DESC;
```

### Retention — weekly retention rate
```sql
WITH w AS (
    SELECT DATE_TRUNC('week', session_date)::DATE wk,
           SUM(sessions) s, SUM(new_users) nu
    FROM raw_ga4_sessions GROUP BY wk
)
SELECT wk,
       ROUND((s - nu)::NUMERIC / NULLIF(s, 0) * 100, 2) AS retention_rate_pct
FROM w ORDER BY wk;
```

### Alerts — active unresolved alerts
```sql
SELECT alert_type, severity, message, created_at
FROM alerts
WHERE is_resolved = FALSE
ORDER BY created_at DESC;
```
