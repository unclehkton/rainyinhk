# rainy

Hong Kong district rainy-day lookup.

Ask one district for one or more dates. Each day comes back as millimetres and whether it was rainy (≥ 0.2 mm). Missing HKO values are `null` with `error: "no_data"`, not dry.

The API covers **18 District Councils + a Lantau Island split** (19 keys). Requires an API key in a header (`X-API-Key` or `Authorization: Bearer`). Query-string `?key=` is not accepted. Wrong key → 401. Dates outside the table → `out_of_range`. A date inside the table with no row → `data_gap`.

```text
GET https://hk-rainy-day.ngcheukhim.workers.dev/rainy?district=Wan%20Chai&dates=2024-04-20,2024-04-19
Authorization: Bearer YOUR_KEY
```

`date=` still works for a single day. The key is for a backend caller, not a public web app: CORS is `*` and a shared key cannot be kept secret in browser JavaScript. Details: `hk_rainfall_pipeline/HANDOFF.md`.
