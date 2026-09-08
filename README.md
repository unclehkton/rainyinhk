# rainy

Hong Kong district rainy-day lookup.

For district D on date T: was T rainy, and was T−1 rainy?

```text
GET https://hk-rainy-day.ngcheukhim.workers.dev/rainy?date=YYYY-MM-DD&district=Wan%20Chai
```

Use `two_day_rainy`. If `data_ok` is false or flags are null → unknown.

Details: `hk_rainfall_pipeline/HANDOFF.md`.
