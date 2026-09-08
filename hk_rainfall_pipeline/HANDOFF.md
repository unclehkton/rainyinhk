# Handoff: Hong Kong district rainy-day table

## Why there were two files before

Those were analysis exports (Excel workbook + a raw district CSV). They are **not** the interface for an application.

Your programme should read **one table** only:

| File | Role |
|---|---|
| `data/rainy_day_lookup.csv` | Canonical table. One row = one district + one calendar day. |
| `data/rainfall.db` | Same table as SQLite (`rainy_day_lookup`), better for queries. |
| `update_rainfall.py` | Refresh job. Not used at request time. |
| `rainy_day.py` | Helper: `check_rainy(date, district)`. |

The large `.xlsx` is optional human review. Do not load it in production.

## Where to put the files

Keep this folder together and point the app at it.

Recommended layout inside **your** repo or server:

```
<your-app>/
  data/hk_rainfall/
    rainy_day_lookup.csv
    rainfall.db
  jobs/
    update_rainfall.py
    config.py
    rainy_day.py
```

Do not store the lookup on a laptop Downloads folder. Options that work:

1. **Application data directory** next to the service that answers “was it rainy?” (best).
2. **SQLite or Postgres** — load `rainy_day_lookup` and query by `(district_en, date)`.
3. Object storage only if the app can read it on every request (S3/GCS). Not required.

This pipeline currently writes to:

`hk_rainfall_pipeline/data/rainy_day_lookup.csv`
`hk_rainfall_pipeline/data/rainfall.db`

Copy those two files into the path above after each refresh.

The live app query is the Worker, not a file on disk:

`GET https://hk-rainy-day.ngcheukhim.workers.dev/rainy?district=Wan%20Chai&dates=2024-04-20,2024-04-19`

Each requested date returns `rainfall_mm` and `is_rainy`. Null means unknown (HKO has not published), not dry.

D1 table `rainy_day_lookup` is the same table. Rebuild D1 with `cloudflare/build_seed.py` after `update_rainfall.py`.

## API district mapping (18 District Councils)

Pass `district` as the **canonical English** name, the **中文** name, or an alias. The Worker always returns `district` (English) and `district_zh`.

Space in English names is `%20` in the URL (`Wan%20Chai`). Chinese names must be URL-encoded.

| `district` (canonical) | 中文 (accepted) | Other accepted aliases | Rainfall source |
|---|---|---|---|
| `Central and Western` | 中西區 | `central` | The Peak `VP1` |
| `Wan Chai` | 灣仔區 | `wanchai`, 灣仔 | The Peak `VP1` (reference; no HKO site in the district) |
| `Eastern` | 東區 | | Shau Kei Wan `SKW` |
| `Southern` | 南區 | | The Peak `VP1` (reference; no HKO site in the district) |
| `Yau Tsim Mong` | 油尖旺區 | `ytm` | Hong Kong Observatory `HKO`, King's Park `KP` |
| `Sham Shui Po` | 深水埗區 | | Sham Shui Po `SSP` |
| `Kowloon City` | 九龍城區 | | Kai Tak `SE` |
| `Wong Tai Sin` | 黃大仙區 | | Tate's Cairn `TC` |
| `Kwun Tong` | 觀塘區 | | Kai Tak `SE` (reference; no HKO site in the district) |
| `Tsuen Wan` | 荃灣區 | | Tai Mo Shan `TMS`, Tsuen Wan `TWN` |
| `Tuen Mun` | 屯門區 | | Tuen Mun Children and Juvenile Home `TU1` |
| `Yuen Long` | 元朗區 | | Lau Fau Shan `LFS`, Shek Kong `SEK`, Wetland Park `WLP` |
| `North` | 北區 | | Sheung Shui `SSH`, Ta Kwu Ling `TKL` |
| `Tai Po` | 大埔區 | | Tai Mei Tuk `PLC` |
| `Sai Kung` | 西貢區 | | Kau Sai Chau `KSC`, Pak Tam Chung `TYW`, Tseung Kwan O `JKB` |
| `Sha Tin` | 沙田區 | `shatin` | Sha Tin `SHA` |
| `Kwai Tsing` | 葵青區 | | Ching Pak House (Tsing Yi) `CPH` |
| `Islands` | 離島區 | | Cheung Chau `CCH`, Peng Chau `PEN`, Waglan Island `WGL` |
| `Lantau Island` | 大嶼山 | `lantau`, 大嶼山區 | Airport `HKA` |

English matching is case-insensitive (`wan chai` → `Wan Chai`). An unknown `district` still returns 200, with `rainfall_mm` and `is_rainy` null for every requested date.

`Lantau Island` is an API split of Islands District, not a 19th District Council. `Islands` / 離島區 is the rest of that district (Cheung Chau, Peng Chau, Waglan). The enquiry itself needs **no API key**.

## Rainy-day definition (do not change in the app)

Agreed rules already applied in the table:

- 微量 / Trace = **0 mm**
- A day is rainy only if district rainfall **≥ 0.2 mm**
- Wan Chai and Southern use **The Peak (`VP1`)**
- Kwun Tong uses **Kai Tak (`SE`)**
- Lantau Island uses **Hong Kong International Airport (`HKA`)**
- Other Islands District uses **Cheung Chau (`CCH`)**, **Peng Chau (`PEN`)**, **Waglan Island (`WGL`)**
- Other districts use the official stations sited there
- Missing HKO values are **not** treated as dry

Columns the programme should use:

| Column | Type | Meaning |
|---|---|---|
| `date` | `YYYY-MM-DD` | Observation date, Hong Kong calendar (UTC+8) |
| `district_en` | text | One of the 18 District Council names |
| `rainfall_mm` | float or empty | District mean after Trace=0 and &lt;0.2→0 |
| `data_ok` | 1/0 | 1 if at least one assigned station published a value |
| `is_rainy` | 1/0/empty | 1 if `rainfall_mm >= 0.2`. Empty when `data_ok=0` |
| `prev_date` | date | Calendar day before `date` |
| `prev_is_rainy` | 1/0/empty | Same rule for the previous day |
| `two_day_rainy` | 1/0/empty | 1 only if **both** today and yesterday are rainy and both `data_ok` |

Empty / NULL means “unknown”, not “not rainy”.

## How the programme should decide

The Worker returns one object per requested date:

```
GET /rainy?district=D&dates=T1,T2,...

for each day:
  if missing or not data_ok → rainfall_mm = null, is_rainy = null   # unknown
  else rainfall_mm is the district millimetres
       is_rainy is true iff rainfall_mm ≥ 0.2
```

To ask “was T and T−1 rainy?”, pass both dates in one enquiry and read each day’s `is_rainy`.

Python (this folder):

```python
from rainy_day import check_rainy

info = check_rainy("2026-08-31", "Wan Chai")
# info["is_rainy"], info["prev_is_rainy"], info["two_day_rainy"]
```

CLI:

```bash
python3 rainy_day.py 2026-08-31 "Kwun Tong"
python3 rainy_day.py 2026-08-31 灣仔區
```

SQL:

```sql
SELECT date, district_en, rainfall_mm, is_rainy, prev_is_rainy, two_day_rainy
FROM rainy_day_lookup
WHERE district_en = 'Wan Chai'
  AND date = '2026-08-31';
```

District names must match the 18-row mapping table above (or use `rainy_day.canonical_district()` / `district_zh`).

## How often to update

The source you chose — [Daily total rainfall, DATA.GOV.HK / HKO](https://data.gov.hk/en-data/dataset/hk-hko-rss-daily-total-rainfall) — is **quality-controlled climate data updated monthly**, not a live gauge feed.

| Need | Cadence | Why |
|---|---|---|
| This table (official daily totals) | **Monthly rebuild**, plus a **weekly cheap check** | Dataset frequency is monthly. Current-year CSVs often gain a completed month around early/mid month. Automatic stations can lag HQ by weeks (e.g. Aug 2026 still blank at many AWS on 4 Sep 2026). |
| “Was yesterday rainy?” for operations | **Do not rely on this source alone** | Yesterday is often unpublished here until the monthly QC pass. Use HKO automatic-station / regional rainfall products if you need T+1. |

Practical schedule:

1. Cron weekly: `python3 update_rainfall.py --check-only` and rebuild if `Last-Modified` changed.
2. Cron monthly on the **10th, 09:00 Asia/Hong_Kong**: `python3 update_rainfall.py`
3. After the job, atomically replace `data/rainy_day_lookup.csv` and `data/rainfall.db` in the app directory.

Example crontab (Hong Kong time):

```cron
0 9 10 * * /usr/bin/python3 /opt/hk_rainfall/update_rainfall.py >> /var/log/hk_rainfall.log 2>&1
0 9 * * 1 /usr/bin/python3 /opt/hk_rainfall/update_rainfall.py --check-only >> /var/log/hk_rainfall.log 2>&1
```

Rebuild command from this folder:

```bash
python3 update_rainfall.py
```

## What “unknown” looks like

If `data_ok = 0`, `rainfall_mm` is empty. That is common for the latest 2–6 weeks at automatic stations. The programme must branch to UNKNOWN, retry later, or fall back to another feed — never `is_rainy = false`.

## Source URLs the updater hits

```
https://data.weather.gov.hk/weatherAPI/hko_data/csdi/dataset/daily_{CODE}_RF_ALL.csv
https://data.weather.gov.hk/weatherAPI/hko_data/csdi/dataset/daily_{CODE}_RF_{YEAR}.csv
```

25 station codes are listed in `config.py`.
