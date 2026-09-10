#!/usr/bin/env python3
"""Build cloudflare/seed.sql from data/rainy_day_lookup.csv (or rainfall.db).

Default is a full wipe+insert for first-time bootstrap. Scheduled D1 updates
pass --from-remote (or --existing-json/--existing-csv) so only new or changed
lookup rows are written.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "data" / "rainy_day_lookup.csv"
DB_PATH = ROOT / "data" / "rainfall.db"
HERE = Path(__file__).resolve().parent
OUT_PATH = HERE / "seed.sql"
STATS_PATH = HERE / "seed_stats.json"
BATCH = 80
DUMP_PAGE = 4000
IGNORE_COMPARE_COLS = {"refreshed_at_utc"}

COLS = [
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
INT_COLS = {
    "n_stations",
    "n_stations_with_data",
    "n_nonzero_stations",
    "data_ok",
    "is_rainy",
    "prev_data_ok",
    "prev_is_rainy",
    "two_day_rainy",
}
REAL_COLS = {"pct_nonzero_stations", "rainfall_mm", "wet_limit_mm", "prev_rainfall_mm"}
COMPARE_COLS = [c for c in COLS if c not in IGNORE_COMPARE_COLS]


def coverage_from_lookup(df: pd.DataFrame) -> dict:
    dates = pd.to_datetime(df["date"], errors="coerce")
    refreshed = df["refreshed_at_utc"].dropna() if "refreshed_at_utc" in df.columns else pd.Series(dtype=str)
    min_date = dates.min()
    max_date = dates.max()
    return {
        "rows": int(len(df)),
        "districts": int(df["district_en"].nunique()) if len(df) else 0,
        "min_date": None if dates.empty or pd.isna(min_date) else pd.Timestamp(min_date).strftime("%Y-%m-%d"),
        "max_date": None if dates.empty or pd.isna(max_date) else pd.Timestamp(max_date).strftime("%Y-%m-%d"),
        "refreshed_at_utc": None if refreshed.empty else str(refreshed.max()),
    }


def load() -> pd.DataFrame:
    if DB_PATH.exists():
        df = pd.read_sql_query("SELECT * FROM rainy_day_lookup", sqlite3.connect(DB_PATH))
    elif CSV_PATH.exists():
        df = pd.read_csv(CSV_PATH)
    else:
        raise FileNotFoundError("run update_rainfall.py first")
    return df


def _is_null(value) -> bool:
    if value is None or value == "":
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def normalize_cell(value, col: str):
    if _is_null(value):
        return None
    if col in {"date", "prev_date"}:
        text = str(value).strip()
        if text.lower() in {"nat", "nan", "none"}:
            return None
        return text[:10]
    if col in INT_COLS:
        return int(value)
    if col in REAL_COLS:
        return round(float(value), 6)
    return str(value)


def _pk(row) -> tuple[str, str]:
    return (normalize_cell(row["date"], "date"), str(row["district_en"]))


def _signature(row) -> tuple:
    return tuple(normalize_cell(row[c], c) for c in COMPARE_COLS)


def _index_lookup(df: pd.DataFrame) -> dict[tuple[str, str], tuple]:
    if df is None or len(df) == 0:
        return {}
    missing = [c for c in COMPARE_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"lookup table missing columns: {missing}")
    return {_pk(row): _signature(row) for _, row in df.iterrows()}


def changed_rows(existing: pd.DataFrame, incoming: pd.DataFrame) -> pd.DataFrame:
    """Rows in incoming that are new or whose compared columns differ.

    refreshed_at_utc is ignored so a no-op rebuild does not rewrite D1.
    """
    if incoming is None or len(incoming) == 0:
        return incoming.copy() if incoming is not None else pd.DataFrame(columns=COLS)
    old = _index_lookup(existing)
    keep = [old.get(_pk(row)) != _signature(row) for _, row in incoming.iterrows()]
    return incoming.loc[keep].reset_index(drop=True)


def removed_keys(existing: pd.DataFrame, incoming: pd.DataFrame) -> list[tuple[str, str]]:
    if existing is None or len(existing) == 0:
        return []
    new_pks = {_pk(row) for _, row in incoming.iterrows()} if incoming is not None and len(incoming) else set()
    return sorted(_index_lookup(existing).keys() - new_pks)


def sql_lit(value, col: str) -> str:
    if _is_null(value):
        return "NULL"
    if col in INT_COLS:
        return str(int(value))
    if col in REAL_COLS:
        return repr(float(value))
    text = str(value)
    if col in {"date", "prev_date"}:
        text = text[:10]
        if text.lower() in {"nat", "nan", "none"}:
            return "NULL"
    return "'" + text.replace("'", "''") + "'"


def _insert_lookup_sql(df: pd.DataFrame, *, replace: bool) -> list[str]:
    verb = "INSERT OR REPLACE INTO" if replace else "INSERT INTO"
    lines = []
    n = len(df)
    for start in range(0, n, BATCH):
        chunk = df.iloc[start : start + BATCH]
        values = []
        for _, row in chunk.iterrows():
            vals = ",".join(sql_lit(row[c], c) for c in COLS)
            values.append(f"({vals})")
        lines.append(verb + " rainy_day_lookup (" + ",".join(COLS) + ") VALUES\n" + ",\n".join(values) + ";")
    return lines


def _pipeline_meta_sql(cov: dict, *, replace: bool) -> str:
    verb = "INSERT OR REPLACE INTO" if replace else "INSERT INTO"
    return (
        verb
        + " pipeline_meta (id, rows, districts, min_date, max_date, refreshed_at_utc) VALUES ("
        f"1,{cov['rows']},{cov['districts']},"
        f"{sql_lit(cov['min_date'], 'date')},"
        f"{sql_lit(cov['max_date'], 'date')},"
        f"{sql_lit(cov['refreshed_at_utc'], 'refreshed_at_utc')}"
        ");"
    )


def _delete_keys_sql(keys: list[tuple[str, str]]) -> list[str]:
    lines = []
    for start in range(0, len(keys), BATCH):
        chunk = keys[start : start + BATCH]
        tuples = ",".join(
            f"({sql_lit(date, 'date')},{sql_lit(district, 'district_en')})" for date, district in chunk
        )
        lines.append(f"DELETE FROM rainy_day_lookup WHERE (date, district_en) IN ({tuples});")
    return lines


def render_full_seed(df: pd.DataFrame) -> tuple[str, dict]:
    cov = coverage_from_lookup(df)
    lines = [
        "-- Generated by build_seed.py. Do not edit by hand.",
        "DELETE FROM rainy_day_lookup;",
        "DELETE FROM pipeline_meta;",
        *_insert_lookup_sql(df, replace=False),
        _pipeline_meta_sql(cov, replace=False),
    ]
    stats = {
        "mode": "full",
        "upserts": int(len(df)),
        "deletes": int(len(df)),
        "noop": False,
        "coverage": cov,
    }
    return "\n".join(lines) + "\n", stats


def render_delta_seed(incoming: pd.DataFrame, existing: pd.DataFrame) -> tuple[str, dict]:
    cov = coverage_from_lookup(incoming)
    upserts = changed_rows(existing, incoming)
    deletions = removed_keys(existing, incoming)
    stats = {
        "mode": "delta",
        "upserts": int(len(upserts)),
        "deletes": int(len(deletions)),
        "noop": len(upserts) == 0 and len(deletions) == 0,
        "coverage": cov,
    }
    if stats["noop"]:
        sql = "-- Generated by build_seed.py (delta noop). 0 D1 writes.\n"
        return sql, stats
    lines = ["-- Generated by build_seed.py (delta). Do not edit by hand."]
    lines.extend(_delete_keys_sql(deletions))
    lines.extend(_insert_lookup_sql(upserts, replace=True))
    lines.append(_pipeline_meta_sql(cov, replace=True))
    return "\n".join(lines) + "\n", stats


def _extract_json_payload(text: str):
    decoder = json.JSONDecoder()
    for idx, char in enumerate(text):
        if char in "[{":
            try:
                payload, _end = decoder.raw_decode(text[idx:])
            except json.JSONDecodeError:
                continue
            return payload
    raise ValueError("no JSON array/object in wrangler output")


def load_existing_json(text: str) -> pd.DataFrame:
    payload = _extract_json_payload(text)
    rows: list[dict] = []
    if isinstance(payload, list):
        if payload and isinstance(payload[0], dict) and "results" in payload[0]:
            for block in payload:
                rows.extend(block.get("results") or [])
        else:
            rows = [row for row in payload if isinstance(row, dict)]
    elif isinstance(payload, dict) and "results" in payload:
        rows = list(payload.get("results") or [])
    else:
        raise ValueError("unrecognised wrangler JSON")
    if not rows:
        return pd.DataFrame(columns=COLS)
    return pd.DataFrame(rows)


def parse_wrangler_json(stdout: str):
    return _extract_json_payload(stdout)


def wrangler_d1_json(sql: str) -> list:
    proc = subprocess.run(
        [
            "npx",
            "wrangler",
            "d1",
            "execute",
            "hk-rainy-day",
            "--remote",
            "--json",
            "--command",
            sql,
        ],
        cwd=HERE,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(f"wrangler d1 execute failed: {detail}")
    payload = parse_wrangler_json(proc.stdout)
    if not isinstance(payload, list):
        raise RuntimeError("wrangler d1 execute did not return a JSON array")
    return payload


def dump_remote_lookup(page: int = DUMP_PAGE) -> pd.DataFrame:
    rows: list[dict] = []
    offset = 0
    while True:
        payload = wrangler_d1_json(
            "SELECT * FROM rainy_day_lookup "
            f"ORDER BY date, district_en LIMIT {int(page)} OFFSET {int(offset)}"
        )
        chunk = list(payload[0].get("results") or [])
        rows.extend(chunk)
        if len(chunk) < page:
            break
        offset += page
    if not rows:
        return pd.DataFrame(columns=COLS)
    return pd.DataFrame(rows)


def _require_cols(df: pd.DataFrame) -> None:
    missing = [c for c in COLS if c not in df.columns]
    if missing:
        raise SystemExit(f"lookup table missing columns: {missing}")


def _write_outputs(sql: str, stats: dict) -> None:
    OUT_PATH.write_text(sql, encoding="utf-8")
    STATS_PATH.write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")
    print(
        f"wrote {OUT_PATH} (mode={stats['mode']}, upserts={stats['upserts']}, "
        f"deletes={stats['deletes']}, noop={str(stats['noop']).lower()}, batch={BATCH})"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build D1 seed SQL from the local lookup table")
    parser.add_argument(
        "--full",
        action="store_true",
        help="DELETE + INSERT every lookup row (bootstrap / recovery)",
    )
    parser.add_argument(
        "--existing-json",
        type=Path,
        help="Current D1 lookup as wrangler --json output, for a delta seed",
    )
    parser.add_argument(
        "--existing-csv",
        type=Path,
        help="Current D1 lookup as CSV, for a delta seed",
    )
    parser.add_argument(
        "--from-remote",
        action="store_true",
        help="Dump remote D1 lookup and write only new/changed rows",
    )
    args = parser.parse_args(argv)

    df = load()
    _require_cols(df)

    existing_flags = [bool(args.existing_json), bool(args.existing_csv), bool(args.from_remote)]
    if sum(existing_flags) > 1:
        raise SystemExit("use only one of --from-remote, --existing-json, --existing-csv")

    if args.full or not any(existing_flags):
        sql, stats = render_full_seed(df)
        _write_outputs(sql, stats)
        return 0

    if args.from_remote:
        existing = dump_remote_lookup()
        print(f"dumped {len(existing)} remote D1 lookup rows")
    elif args.existing_json:
        existing = load_existing_json(args.existing_json.read_text(encoding="utf-8"))
    else:
        existing = pd.read_csv(args.existing_csv)

    sql, stats = render_delta_seed(df, existing)
    _write_outputs(sql, stats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
