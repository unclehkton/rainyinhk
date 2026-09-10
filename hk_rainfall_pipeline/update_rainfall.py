#!/usr/bin/env python3
"""
Refresh HK district rainy-day lookup from HKO / DATA.GOV.HK.

Writes one application table:
  data/rainy_day_lookup.csv
  data/rainfall.db  (table rainy_day_lookup)

Usage:
  python3 update_rainfall.py              # fetch source + rebuild
  python3 update_rainfall.py --from-csv PATH  # rebuild from an existing district-daily CSV
  python3 update_rainfall.py --check-only     # compare Last-Modified/ETag; exit 10 if changed
"""

from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import re
import sqlite3
import sys
import time
from pathlib import Path

import pandas as pd
import requests

from config import (
    CSDI_ALL,
    CSDI_YEAR,
    DIST_ZH,
    DISTRICTS,
    REFERENCE_STATIONS,
    START_YEAR,
    STATION_BY_CODE,
    STATIONS,
    WET_LIMIT_MM,
)

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
RAW = DATA / "raw"
LOOKUP_CSV = DATA / "rainy_day_lookup.csv"
DB_PATH = DATA / "rainfall.db"
META_PATH = DATA / "last_refresh.json"
FINGERPRINT_PATH = DATA / "source_fingerprint.json"
FINGERPRINT_STATIONS = ("HKO", "VP1", "SE")
CHECK_CHANGED_EXIT = 10

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "hk-rainfall-pipeline/1.0"})


def parse_rain(val):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return pd.NA
    s = str(val).strip()
    if s == "" or s == "***":
        return pd.NA
    if s.lower() in {"trace", "微量", "微量*"}:
        return 0.0
    s = s.replace("#", "").replace("*", "").strip()
    try:
        return float(s)
    except ValueError:
        return pd.NA


def download(url: str, dest: Path) -> tuple[Path, str | None]:
    dest.parent.mkdir(parents=True, exist_ok=True)
    last_mod = None
    for attempt in range(4):
        try:
            r = SESSION.get(url, timeout=60)
            r.raise_for_status()
            last_mod = r.headers.get("Last-Modified")
            dest.write_bytes(r.content)
            return dest, last_mod
        except Exception as exc:
            print(f"  retry {attempt + 1} {url} ({exc})", file=sys.stderr)
            time.sleep(1.2 * (attempt + 1))
    raise RuntimeError(f"download failed: {url}")


def head_source_headers(url: str) -> dict[str, str | None]:
    try:
        r = SESSION.head(url, timeout=20, allow_redirects=True)
        return {
            "last_modified": r.headers.get("Last-Modified"),
            "etag": r.headers.get("ETag"),
        }
    except Exception:
        return {"last_modified": None, "etag": None}


def head_last_modified(url: str) -> str | None:
    return head_source_headers(url).get("last_modified")


def collect_source_fingerprint(year: int, header_fn=head_source_headers) -> dict:
    sources = {}
    for code in FINGERPRINT_STATIONS:
        url_all = CSDI_ALL.format(code=code)
        sources[f"{code}_ALL"] = {"url": url_all, **header_fn(url_all)}
        url_year = CSDI_YEAR.format(code=code, year=year)
        sources[f"{code}_{year}"] = {"url": url_year, **header_fn(url_year)}
    return {
        "year": year,
        "collected_at_utc": dt.datetime.now(dt.timezone.utc)
        .replace(microsecond=0)
        .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sources": sources,
    }


def fingerprint_identity(fp: dict | None) -> dict[str, tuple[str | None, str | None]]:
    sources = (fp or {}).get("sources") or {}
    return {
        key: (val.get("last_modified"), val.get("etag"))
        for key, val in sorted(sources.items())
    }


def fingerprint_has_headers(fp: dict | None) -> bool:
    for last_modified, etag in fingerprint_identity(fp).values():
        if last_modified or etag:
            return True
    return False


def fingerprint_changed(stored: dict | None, current: dict | None) -> bool:
    if not fingerprint_has_headers(current):
        return False
    if not stored or not stored.get("sources"):
        return True
    return fingerprint_identity(stored) != fingerprint_identity(current)


def load_stored_fingerprint() -> dict | None:
    if not FINGERPRINT_PATH.exists():
        return None
    try:
        return json.loads(FINGERPRINT_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_source_fingerprint(fp: dict) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    FINGERPRINT_PATH.write_text(json.dumps(fp, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {FINGERPRINT_PATH}")


def run_check_only(year: int) -> int:
    current = collect_source_fingerprint(year)
    stored = load_stored_fingerprint()
    print("Source Last-Modified / ETag (sample stations HKO, VP1, SE):")
    for key, val in current.get("sources", {}).items():
        print(f"  {key} Last-Modified={val.get('last_modified')} ETag={val.get('etag')}")
    if stored:
        print(f"Stored fingerprint: {FINGERPRINT_PATH}")
    else:
        print("Stored fingerprint: none")
    print("Official dataset update frequency: monthly.")
    if not fingerprint_has_headers(current):
        print("Status: headers_unavailable (skip rebuild)")
        return 0
    if fingerprint_changed(stored, current):
        print("Status: changed")
        print("Rebuild required.")
        return CHECK_CHANGED_EXIT
    print("Status: unchanged")
    return 0


def parse_csdi(path: Path) -> pd.DataFrame:
    text = path.read_bytes().decode("utf-8-sig", errors="replace")
    lines = text.splitlines()
    header_idx = next(
        (i for i, line in enumerate(lines) if line.startswith("Year/") or line.startswith("年/Year")),
        None,
    )
    if header_idx is None:
        raise ValueError(f"no header in {path}")
    data_lines = [line for line in lines[header_idx + 1 :] if re.match(r"^\d{4},", line)]
    buf = "year,month,day,hour,minute,second,timezone,value,completeness\n" + "\n".join(data_lines)
    return pd.read_csv(io.StringIO(buf), dtype=str)


def load_station(code: str, years: list[int]) -> pd.DataFrame:
    frames = []
    dest_all = RAW / f"{code}_ALL.csv"
    download(CSDI_ALL.format(code=code), dest_all)
    frames.append(parse_csdi(dest_all))
    for year in years:
        dest_y = RAW / f"{code}_{year}.csv"
        download(CSDI_YEAR.format(code=code, year=year), dest_y)
        frames.append(parse_csdi(dest_y))
    df = pd.concat(frames, ignore_index=True)
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df["month"] = pd.to_numeric(df["month"], errors="coerce")
    df["day"] = pd.to_numeric(df["day"], errors="coerce")
    df = df.dropna(subset=["year", "month", "day"])
    df = df[df["year"] >= START_YEAR]
    df["date"] = pd.to_datetime(
        dict(year=df["year"].astype(int), month=df["month"].astype(int), day=df["day"].astype(int)),
        errors="coerce",
    )
    df = df.dropna(subset=["date"]).drop_duplicates(subset=["date"], keep="last")
    meta = STATION_BY_CODE[code]
    df["station_code"] = code
    df["station_name_en"] = meta[1]
    df["district_en"] = meta[3]
    df["rainfall_original"] = df["value"].fillna("").astype(str).str.strip()
    df["rainfall_mm"] = df["rainfall_original"].map(parse_rain)
    df["rainfall_mm_for_stats"] = df["rainfall_mm"].where(
        df["rainfall_mm"].isna(),
        df["rainfall_mm"].mask(df["rainfall_mm"] < WET_LIMIT_MM, 0.0),
    )
    return df[
        [
            "date",
            "station_code",
            "station_name_en",
            "district_en",
            "rainfall_original",
            "rainfall_mm",
            "rainfall_mm_for_stats",
        ]
    ]


def build_district_daily(station_daily: pd.DataFrame) -> pd.DataFrame:
    station_daily = station_daily.copy()
    station_daily["has_data"] = station_daily["rainfall_mm_for_stats"].notna()
    station_daily["is_wet"] = station_daily["rainfall_mm_for_stats"].fillna(0) >= WET_LIMIT_MM

    contrib = station_daily.copy()
    contrib["assignment"] = "located_in_district"
    extras = []
    for dest, code in REFERENCE_STATIONS.items():
        block = station_daily[station_daily["station_code"] == code].copy()
        block["district_en"] = dest
        block["assignment"] = "reference_station"
        extras.append(block)
    contrib = pd.concat([contrib] + extras, ignore_index=True)

    g = contrib.groupby(["date", "district_en"], dropna=False)
    observed = g.agg(
        n_stations=("station_code", "nunique"),
        n_stations_with_data=("has_data", "sum"),
        n_nonzero_stations=("is_wet", "sum"),
        rainfall_mm=("rainfall_mm_for_stats", "mean"),
        source_station_codes=("station_code", lambda s: ",".join(sorted(set(s)))),
        assignment=("assignment", lambda s: "reference_station" if set(s) == {"reference_station"} else "located_in_district"),
    ).reset_index()

    dates = pd.DataFrame({"date": pd.date_range(station_daily["date"].min(), station_daily["date"].max(), freq="D")})
    grid = dates.merge(pd.DataFrame({"district_en": [d[0] for d in DISTRICTS]}), how="cross")
    dist = grid.merge(observed, on=["date", "district_en"], how="left")
    dist["district_zh"] = dist["district_en"].map(DIST_ZH)
    dist["assignment"] = dist["district_en"].map(
        lambda d: "reference_station" if d in REFERENCE_STATIONS else "located_in_district"
    )
    for col in ["n_stations", "n_stations_with_data", "n_nonzero_stations"]:
        dist[col] = dist[col].fillna(0).astype(int)
    return dist


def build_lookup(dist: pd.DataFrame) -> pd.DataFrame:
    out = dist.copy()
    out["date"] = pd.to_datetime(out["date"])
    out["data_ok"] = out["n_stations_with_data"] > 0
    out["is_rainy"] = pd.NA
    mask = out["data_ok"]
    out.loc[mask, "is_rainy"] = out.loc[mask, "rainfall_mm"] >= WET_LIMIT_MM
    out["pct_nonzero_stations"] = out.apply(
        lambda r: (r["n_nonzero_stations"] / r["n_stations_with_data"])
        if r["n_stations_with_data"] > 0
        else pd.NA,
        axis=1,
    )
    out = out.sort_values(["district_en", "date"])
    out["prev_date"] = out.groupby("district_en")["date"].shift(1)
    out["prev_rainfall_mm"] = out.groupby("district_en")["rainfall_mm"].shift(1)
    out["prev_data_ok"] = out.groupby("district_en")["data_ok"].shift(1)
    out["prev_is_rainy"] = out.groupby("district_en")["is_rainy"].shift(1)
    both_ok = out["data_ok"] & out["prev_data_ok"].fillna(False)
    out["two_day_rainy"] = pd.NA
    out.loc[both_ok, "two_day_rainy"] = (
        out.loc[both_ok, "is_rainy"].astype(bool) & out.loc[both_ok, "prev_is_rainy"].astype(bool)
    )
    out["wet_limit_mm"] = WET_LIMIT_MM
    out["refreshed_at_utc"] = (
        dt.datetime.now(dt.timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    cols = [
        "date",
        "district_en",
        "district_zh",
        "assignment",
        "source_station_codes",
        "n_stations",
        "n_stations_with_data",
        "n_nonzero_stations",
        "pct_nonzero_stations",
        "rainfall_mm",
        "wet_limit_mm",
        "data_ok",
        "is_rainy",
        "prev_date",
        "prev_rainfall_mm",
        "prev_data_ok",
        "prev_is_rainy",
        "two_day_rainy",
        "refreshed_at_utc",
    ]
    return out[cols].sort_values(["date", "district_en"]).reset_index(drop=True)


def write_outputs(lookup: pd.DataFrame) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    csv_out = lookup.copy()
    for col in ["date", "prev_date"]:
        csv_out[col] = pd.to_datetime(csv_out[col], errors="coerce").dt.strftime("%Y-%m-%d")
    for col in ["is_rainy", "prev_is_rainy", "two_day_rainy", "data_ok", "prev_data_ok"]:
        csv_out[col] = csv_out[col].map(lambda v: "" if pd.isna(v) else ("1" if bool(v) else "0"))
    csv_out.to_csv(LOOKUP_CSV, index=False)

    conn = sqlite3.connect(DB_PATH)
    db = lookup.copy()
    for col in ["date", "prev_date"]:
        db[col] = pd.to_datetime(db[col], errors="coerce").dt.strftime("%Y-%m-%d")
    for col in ["is_rainy", "prev_is_rainy", "two_day_rainy", "data_ok", "prev_data_ok"]:
        db[col] = db[col].map(lambda v: None if pd.isna(v) else (1 if bool(v) else 0))
    db.to_sql("rainy_day_lookup", conn, if_exists="replace", index=False)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_rainy_lookup ON rainy_day_lookup(district_en, date)"
    )
    conn.commit()
    conn.close()
    print(f"wrote {LOOKUP_CSV} ({len(lookup)} rows)")
    print(f"wrote {DB_PATH} table rainy_day_lookup")
    dates = pd.to_datetime(lookup["date"], errors="coerce")
    META_PATH.write_text(
        json.dumps(
            {
                "refreshed_at_utc": dt.datetime.now(dt.timezone.utc)
                .replace(microsecond=0)
                .strftime("%Y-%m-%dT%H:%M:%SZ"),
                "rows": int(len(lookup)),
                "min_date": dates.min().strftime("%Y-%m-%d") if len(dates) else None,
                "max_date": dates.max().strftime("%Y-%m-%d") if len(dates) else None,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote {META_PATH}")


def lookup_from_existing_district_csv(path: Path) -> pd.DataFrame:
    raw = pd.read_csv(path, parse_dates=["date"])
    dist = pd.DataFrame(
        {
            "date": raw["date"],
            "district_en": raw["district_en"],
            "district_zh": raw["district_zh"],
            "assignment": raw["assignment"],
            "source_station_codes": raw["source_station_codes"],
            "n_stations": raw["n_stations"],
            "n_stations_with_data": raw["n_stations_with_data"],
            "n_nonzero_stations": raw["n_nonzero_stations"],
            "rainfall_mm": raw["district_avg_rainfall_mm"],
        }
    )
    return build_lookup(dist)


def main() -> int:
    parser = argparse.ArgumentParser(description="Update HK rainy-day lookup table")
    parser.add_argument("--from-csv", type=Path, help="Rebuild lookup from district-daily CSV")
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Compare source Last-Modified/ETag with the stored fingerprint. Exit 10 if HKO published (rebuild needed).",
    )
    parser.add_argument("--year", type=int, default=dt.date.today().year)
    args = parser.parse_args()

    if args.check_only:
        return run_check_only(args.year)

    if args.from_csv:
        lookup = lookup_from_existing_district_csv(args.from_csv)
        write_outputs(lookup)
        save_source_fingerprint(collect_source_fingerprint(args.year))
        return 0

    years = list(range(START_YEAR, args.year + 1))
    parts = []
    for code, *_ in STATIONS:
        print("fetch", code)
        parts.append(load_station(code, years=[args.year]))
    station_daily = pd.concat(parts, ignore_index=True)
    dist = build_district_daily(station_daily)
    lookup = build_lookup(dist)
    write_outputs(lookup)
    save_source_fingerprint(collect_source_fingerprint(args.year))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
