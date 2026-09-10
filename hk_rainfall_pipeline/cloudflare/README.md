# hk-rainy-day Worker

Ask one district for one or more dates. Each day is rainfall in mm and whether it was rainy (≥ 0.2 mm).

```text
GET /rainy?district=Wan%20Chai&dates=2024-04-20,2024-04-19
Authorization: Bearer YOUR_KEY

GET /rainy?district=灣仔區&date=2024-04-20
X-API-Key: YOUR_KEY
```

```json
{
  "district": "Wan Chai",
  "district_zh": "灣仔區",
  "days": [
    { "date": "2024-04-20", "rainfall_mm": 21, "is_rainy": true, "error": null },
    { "date": "2024-04-19", "rainfall_mm": 0.5, "is_rainy": true, "error": null }
  ]
}
```

If HKO has not published that day, `rainfall_mm` and `is_rainy` are `null` and `error` is `no_data`. Dates outside the table are `out_of_range`. A date inside coverage with no D1 row is `data_gap` (HTTP 500). Missing or wrong API key is HTTP 401. Do not put the key in `?key=`. The secret is the Worker binding `RAINY_API_KEY`, not a git file.

District names: **18 District Councils + Lantau Island split**. `Lantau Island` is Airport `HKA`; `Islands` is CCH/PEN/WGL.

`GET /health` reads the one-row `pipeline_meta` table (row count, date bounds, `refreshed_at_utc`) and is 503 if that snapshot is empty, incomplete, or stale. `GET /rainy` uses the same row for coverage, then an indexed lookup of the requested dates. `GET /` is a cheap liveness probe and does not touch D1.

CORS is `Access-Control-Allow-Origin: *`. A shared API key cannot be kept secret in public frontend JavaScript; use this key from a backend, or put rate limiting / Access in front of anonymous browser traffic.

## One-time setup

From this folder, after `npx wrangler login`:

```bash
npm ci
npx wrangler d1 create hk-rainy-day
# paste database_id into wrangler.toml

npx wrangler d1 execute hk-rainy-day --remote --file=schema.sql --yes
../.venv/bin/python build_seed.py --full
npx wrangler d1 execute hk-rainy-day --remote --file=seed.sql --yes
npx wrangler deploy
```

Refresh job lives in the parent folder (`update_rainfall.py`). Do not scrape HKO from this Worker. Scheduled Actions skip when HKO Last-Modified/ETag is unchanged. When HKO publishes, `build_seed.py --from-remote` upserts only new or changed lookup rows.

```bash
../.venv/bin/python build_seed.py --from-remote   # delta vs live D1
../.venv/bin/python build_seed.py --full          # wipe + insert (bootstrap)
```

## Local

```bash
npm test
npx wrangler d1 execute hk-rainy-day --local --file=schema.sql --yes
npx wrangler d1 execute hk-rainy-day --local --file=seed.sql --yes
npx wrangler dev
```
