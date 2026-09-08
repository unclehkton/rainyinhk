CREATE TABLE IF NOT EXISTS rainy_day_lookup (
  date TEXT NOT NULL,
  district_en TEXT NOT NULL,
  district_zh TEXT,
  assignment TEXT,
  source_station_codes TEXT,
  n_stations INTEGER,
  n_stations_with_data INTEGER,
  n_nonzero_stations INTEGER,
  pct_nonzero_stations REAL,
  rainfall_mm REAL,
  wet_limit_mm REAL,
  data_ok INTEGER,
  is_rainy INTEGER,
  prev_date TEXT,
  prev_rainfall_mm REAL,
  prev_data_ok INTEGER,
  prev_is_rainy INTEGER,
  two_day_rainy INTEGER,
  refreshed_at_utc TEXT,
  PRIMARY KEY (date, district_en)
);

CREATE INDEX IF NOT EXISTS idx_rainy_lookup ON rainy_day_lookup(district_en, date);

CREATE TABLE IF NOT EXISTS pipeline_meta (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  rows INTEGER NOT NULL,
  districts INTEGER NOT NULL,
  min_date TEXT,
  max_date TEXT,
  refreshed_at_utc TEXT
);
