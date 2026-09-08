-- One-shot: fill pipeline_meta from the lookup table (scans once at import time).
-- Request-time Worker reads this one row instead of aggregating 18k lookup rows.
DELETE FROM pipeline_meta;
INSERT INTO pipeline_meta (id, rows, districts, min_date, max_date, refreshed_at_utc)
SELECT 1,
       COUNT(*),
       COUNT(DISTINCT district_en),
       MIN(date),
       MAX(date),
       MAX(refreshed_at_utc)
  FROM rainy_day_lookup;
