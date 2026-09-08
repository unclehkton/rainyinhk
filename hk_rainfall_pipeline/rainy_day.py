#!/usr/bin/env python3
"""Application helper: was this district rainy today and yesterday?"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "data" / "rainfall.db"
CSV_PATH = ROOT / "data" / "rainy_day_lookup.csv"

# Accept a few aliases your programme might send
DISTRICT_ALIASES = {
    "central and western": "Central and Western",
    "central": "Central and Western",
    "中西區": "Central and Western",
    "wan chai": "Wan Chai",
    "wanchai": "Wan Chai",
    "灣仔區": "Wan Chai",
    "灣仔": "Wan Chai",
    "eastern": "Eastern",
    "東區": "Eastern",
    "southern": "Southern",
    "南區": "Southern",
    "yau tsim mong": "Yau Tsim Mong",
    "ytm": "Yau Tsim Mong",
    "油尖旺區": "Yau Tsim Mong",
    "sham shui po": "Sham Shui Po",
    "深水埗區": "Sham Shui Po",
    "kowloon city": "Kowloon City",
    "九龍城區": "Kowloon City",
    "wong tai sin": "Wong Tai Sin",
    "黃大仙區": "Wong Tai Sin",
    "kwun tong": "Kwun Tong",
    "觀塘區": "Kwun Tong",
    "tsuen wan": "Tsuen Wan",
    "荃灣區": "Tsuen Wan",
    "tuen mun": "Tuen Mun",
    "屯門區": "Tuen Mun",
    "yuen long": "Yuen Long",
    "元朗區": "Yuen Long",
    "north": "North",
    "北區": "North",
    "tai po": "Tai Po",
    "大埔區": "Tai Po",
    "sai kung": "Sai Kung",
    "西貢區": "Sai Kung",
    "sha tin": "Sha Tin",
    "shatin": "Sha Tin",
    "沙田區": "Sha Tin",
    "kwai tsing": "Kwai Tsing",
    "葵青區": "Kwai Tsing",
    "islands": "Islands",
    "離島區": "Islands",
}


def canonical_district(name: str) -> str:
    key = name.strip()
    return DISTRICT_ALIASES.get(key.lower(), DISTRICT_ALIASES.get(key, key))


def _load() -> pd.DataFrame:
    if DB_PATH.exists():
        df = pd.read_sql_query("SELECT * FROM rainy_day_lookup", sqlite3.connect(DB_PATH))
    elif CSV_PATH.exists():
        df = pd.read_csv(CSV_PATH)
    else:
        raise FileNotFoundError(f"No lookup table at {DB_PATH} or {CSV_PATH}. Run update_rainfall.py first.")
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    return df


def check_rainy(date: str, district: str) -> dict:
    """Return rainy flags for `date` and the calendar day before, in one district.

    is_rainy / prev_is_rainy / two_day_rainy are True/False when data_ok,
    otherwise None (do not treat missing HKO values as dry).
    """
    date = pd.Timestamp(date).strftime("%Y-%m-%d")
    district = canonical_district(district)
    df = _load()
    rows = df[(df["date"] == date) & (df["district_en"] == district)]
    if rows.empty:
        return {
            "found": False,
            "date": date,
            "district_en": district,
            "is_rainy": None,
            "prev_is_rainy": None,
            "two_day_rainy": None,
            "reason": "no_row",
        }
    r = rows.iloc[0]

    def flag(col):
        v = r[col]
        if v is None or (isinstance(v, float) and pd.isna(v)) or v == "":
            return None
        return bool(int(v)) if str(v) in {"0", "1"} else bool(v)

    return {
        "found": True,
        "date": date,
        "district_en": district,
        "district_zh": r["district_zh"],
        "rainfall_mm": None if pd.isna(r["rainfall_mm"]) else float(r["rainfall_mm"]),
        "data_ok": flag("data_ok"),
        "is_rainy": flag("is_rainy"),
        "prev_date": None if pd.isna(r["prev_date"]) else str(r["prev_date"])[:10],
        "prev_rainfall_mm": None if pd.isna(r["prev_rainfall_mm"]) else float(r["prev_rainfall_mm"]),
        "prev_data_ok": flag("prev_data_ok"),
        "prev_is_rainy": flag("prev_is_rainy"),
        "two_day_rainy": flag("two_day_rainy"),
        "assignment": r["assignment"],
        "source_station_codes": r["source_station_codes"],
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("date", help="YYYY-MM-DD")
    p.add_argument("district", help="e.g. 'Wan Chai' or 灣仔區")
    args = p.parse_args()
    result = check_rainy(args.date, args.district)
    for k, v in result.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()
