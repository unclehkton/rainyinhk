# hk-rainy-day Worker

Answers one question: for district D on date T, was T rainy, and was T−1 rainy?

```text
GET /rainy?date=YYYY-MM-DD&district=Wan%20Chai
```

Use `two_day_rainy`. If `data_ok` is false, `prev_data_ok` is false, or flags are null → unknown. `verdict` is the programme contract:

- `UNKNOWN`
- `RAINY_TWO_DAYS`
- `RAINY_TODAY_ONLY`
- `NOT_RAINY`

District names: English 18-district list, or the Chinese aliases in `src/lookup.js`.

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
