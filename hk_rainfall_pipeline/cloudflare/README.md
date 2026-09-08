# hk-rainy-day Worker

Ask one district for one or more dates. Each day is rainfall in mm and whether it was rainy (≥ 0.2 mm).

```text
GET /rainy?key=YOUR_KEY&district=Wan%20Chai&dates=2024-04-20,2024-04-19
GET /rainy?district=灣仔區&date=2024-04-20
Header: X-API-Key: YOUR_KEY
```

```json
{
  "district": "Wan Chai",
  "district_zh": "灣仔區",
  "days": [
    { "date": "2024-04-20", "rainfall_mm": 21, "is_rainy": true },
    { "date": "2024-04-19", "rainfall_mm": 0.5, "is_rainy": true }
  ]
}
```

If HKO has not published that day, `rainfall_mm` and `is_rainy` are `null` and `error` is `no_data`. Dates outside the table are `out_of_range`. Missing or wrong API key is HTTP 401. The key is the Worker secret `RAINY_API_KEY`, not a git file. District names: the 18 District Councils plus `Lantau Island` (Airport `HKA`); `Islands` is CCH/PEN/WGL.

## One-time setup

From this folder, after `npx wrangler login`:

```bash
npx wrangler d1 create hk-rainy-day
# paste database_id into wrangler.toml

npx wrangler d1 execute hk-rainy-day --remote --file=schema.sql --yes
../.venv/bin/python build_seed.py
npx wrangler d1 execute hk-rainy-day --remote --file=seed.sql --yes
npx wrangler deploy
```

Refresh job lives in the parent folder (`update_rainfall.py`). Do not scrape HKO from this Worker.

## Local

```bash
npm test
npx wrangler d1 execute hk-rainy-day --local --file=schema.sql --yes
npx wrangler d1 execute hk-rainy-day --local --file=seed.sql --yes
npx wrangler dev
```
