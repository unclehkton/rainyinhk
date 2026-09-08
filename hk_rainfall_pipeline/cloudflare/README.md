# hk-rainy-day Worker

Ask one district for one or more dates. Each day is rainfall in mm and whether it was rainy (≥ 0.2 mm).

```text
GET /rainy?district=Wan%20Chai&dates=2024-04-20,2024-04-19
GET /rainy?district=灣仔區&date=2024-04-20
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

If HKO has not published that day, `rainfall_mm` and `is_rainy` are `null` (unknown, not dry). District names: English 18-district list, or the Chinese aliases in `src/lookup.js`.

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
