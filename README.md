# rainy

Hong Kong district rainy-day lookup.

Ask one district for one or more dates. Each day comes back as millimetres and whether it was rainy (≥ 0.2 mm). Missing HKO values are `null` with `error: "no_data"`, not dry.

Requires an API key (`key=`, `X-API-Key`, or `Authorization: Bearer`). Wrong key → 401. Dates outside the table → `out_of_range`.

```text
GET https://hk-rainy-day.ngcheukhim.workers.dev/rainy?key=YOUR_KEY&district=Wan%20Chai&dates=2024-04-20,2024-04-19
```

`date=` still works for a single day. Details: `hk_rainfall_pipeline/HANDOFF.md`.
