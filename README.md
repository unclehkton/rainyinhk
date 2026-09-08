# rainy

Hong Kong district rainy-day lookup.

Ask one district for one or more dates. Each day comes back as millimetres and whether it was rainy (≥ 0.2 mm). Missing HKO values are `null`, not dry.

```text
GET https://hk-rainy-day.ngcheukhim.workers.dev/rainy?district=Wan%20Chai&dates=2024-04-20,2024-04-19
```

`date=` still works for a single day. Public GET — no API key. Details: `hk_rainfall_pipeline/HANDOFF.md`.
