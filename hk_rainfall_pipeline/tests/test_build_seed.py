#!/usr/bin/env python3
"""Coverage row and D1 delta seed (only new/changed lookup rows)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cloudflare"))

from build_seed import (  # noqa: E402
    COLS,
    changed_rows,
    coverage_from_lookup,
    load_existing_json,
    removed_keys,
    render_delta_seed,
    render_full_seed,
)


def _row(
    date: str,
    district: str,
    rainfall: float | None,
    *,
    data_ok: int = 1,
    is_rainy: int | None = 0,
    refreshed: str = "2026-09-08T09:00:00Z",
    prev_date: str | None = None,
    prev_rainfall: float | None = None,
    prev_data_ok: int | None = None,
    prev_is_rainy: int | None = None,
    two_day_rainy: int | None = None,
) -> dict:
    return {
        "date": date,
        "district_en": district,
        "district_zh": "灣仔區" if district == "Wan Chai" else "離島區",
        "assignment": "reference_station" if district == "Wan Chai" else "located_in_district",
        "source_station_codes": "VP1" if district == "Wan Chai" else "CCH,PEN,WGL",
        "n_stations": 1 if district == "Wan Chai" else 3,
        "n_stations_with_data": data_ok,
        "n_nonzero_stations": 1 if is_rainy else 0,
        "pct_nonzero_stations": (1.0 if is_rainy else 0.0) if data_ok else None,
        "rainfall_mm": rainfall,
        "wet_limit_mm": 0.2,
        "data_ok": data_ok,
        "is_rainy": is_rainy,
        "prev_date": prev_date,
        "prev_rainfall_mm": prev_rainfall,
        "prev_data_ok": prev_data_ok,
        "prev_is_rainy": prev_is_rainy,
        "two_day_rainy": two_day_rainy,
        "refreshed_at_utc": refreshed,
    }


def _frame(*rows: dict) -> pd.DataFrame:
    return pd.DataFrame(list(rows), columns=COLS)


class CoverageFromLookupTests(unittest.TestCase):
    def test_summarises_bounds_without_scanning_at_request_time(self):
        df = pd.DataFrame(
            {
                "date": ["2024-01-01", "2024-01-02", "2024-01-02"],
                "district_en": ["Wan Chai", "Wan Chai", "Islands"],
                "refreshed_at_utc": [
                    "2026-09-08T09:00:06Z",
                    "2026-09-08T09:00:06Z",
                    "2026-09-08T09:00:07Z",
                ],
            }
        )
        self.assertEqual(
            coverage_from_lookup(df),
            {
                "rows": 3,
                "districts": 2,
                "min_date": "2024-01-01",
                "max_date": "2024-01-02",
                "refreshed_at_utc": "2026-09-08T09:00:07Z",
            },
        )

    def test_empty_lookup(self):
        df = pd.DataFrame({"date": [], "district_en": [], "refreshed_at_utc": []})
        self.assertEqual(
            coverage_from_lookup(df),
            {
                "rows": 0,
                "districts": 0,
                "min_date": None,
                "max_date": None,
                "refreshed_at_utc": None,
            },
        )


class ChangedRowsTests(unittest.TestCase):
    def test_ignores_refreshed_at_only(self):
        existing = _frame(_row("2026-08-31", "Wan Chai", 0.0, is_rainy=0))
        incoming = _frame(
            _row(
                "2026-08-31",
                "Wan Chai",
                0.0,
                is_rainy=0,
                refreshed="2026-09-10T05:43:23Z",
            )
        )
        self.assertTrue(changed_rows(existing, incoming).empty)
        self.assertEqual(removed_keys(existing, incoming), [])

    def test_inserts_new_month_only(self):
        existing = _frame(_row("2026-08-31", "Wan Chai", 0.0, is_rainy=0))
        incoming = _frame(
            _row("2026-08-31", "Wan Chai", 0.0, is_rainy=0),
            _row(
                "2026-09-01",
                "Wan Chai",
                12.4,
                is_rainy=1,
                prev_date="2026-08-31",
                prev_rainfall=0.0,
                prev_data_ok=1,
                prev_is_rainy=0,
                two_day_rainy=0,
            ),
        )
        delta = changed_rows(existing, incoming)
        self.assertEqual(list(delta["date"]), ["2026-09-01"])
        self.assertEqual(list(delta["district_en"]), ["Wan Chai"])
        self.assertEqual(list(delta["rainfall_mm"]), [12.4])
        self.assertEqual(removed_keys(existing, incoming), [])

    def test_upserts_backfilled_same_date(self):
        existing = _frame(_row("2026-08-31", "Wan Chai", None, data_ok=0, is_rainy=None))
        incoming = _frame(_row("2026-08-31", "Wan Chai", 3.2, data_ok=1, is_rainy=1))
        delta = changed_rows(existing, incoming)
        self.assertEqual(len(delta), 1)
        self.assertEqual(delta.iloc[0]["rainfall_mm"], 3.2)
        self.assertEqual(int(delta.iloc[0]["is_rainy"]), 1)

    def test_treats_empty_existing_as_all_inserts(self):
        incoming = _frame(
            _row("2026-08-31", "Wan Chai", 0.0),
            _row("2026-08-31", "Islands", 1.2, is_rainy=1),
        )
        delta = changed_rows(_frame(), incoming)
        self.assertEqual(len(delta), 2)

    def test_float_and_int_type_noise_is_not_a_change(self):
        existing = _frame(_row("2024-04-20", "Wan Chai", 21.0, is_rainy=1))
        incoming = existing.copy()
        incoming["rainfall_mm"] = incoming["rainfall_mm"].astype(object)
        incoming["is_rainy"] = incoming["is_rainy"].astype(object)
        incoming.at[0, "rainfall_mm"] = 21
        incoming.at[0, "is_rainy"] = True
        self.assertTrue(changed_rows(existing, incoming).empty)

    def test_removed_keys_when_a_row_disappears(self):
        existing = _frame(
            _row("2026-08-31", "Wan Chai", 0.0),
            _row("2026-08-31", "Islands", 0.0),
        )
        incoming = _frame(_row("2026-08-31", "Wan Chai", 0.0))
        self.assertEqual(removed_keys(existing, incoming), [("2026-08-31", "Islands")])
        self.assertTrue(changed_rows(existing, incoming).empty)


class SeedSqlTests(unittest.TestCase):
    def test_full_seed_wipes_lookup(self):
        df = _frame(_row("2026-08-31", "Wan Chai", 0.0))
        sql, stats = render_full_seed(df)
        self.assertEqual(stats["mode"], "full")
        self.assertIn("DELETE FROM rainy_day_lookup;", sql)
        self.assertIn("INSERT INTO rainy_day_lookup", sql)
        self.assertNotIn("INSERT OR REPLACE INTO rainy_day_lookup", sql)

    def test_delta_seed_upserts_only_new_rows_and_refreshes_meta(self):
        existing = _frame(_row("2026-08-31", "Wan Chai", 0.0, is_rainy=0))
        incoming = _frame(
            _row("2026-08-31", "Wan Chai", 0.0, is_rainy=0),
            _row(
                "2026-09-01",
                "Wan Chai",
                12.4,
                is_rainy=1,
                prev_date="2026-08-31",
                prev_rainfall=0.0,
                prev_data_ok=1,
                prev_is_rainy=0,
                two_day_rainy=0,
                refreshed="2026-10-10T01:00:00Z",
            ),
        )
        sql, stats = render_delta_seed(incoming, existing)
        self.assertEqual(stats["mode"], "delta")
        self.assertEqual(stats["upserts"], 1)
        self.assertEqual(stats["deletes"], 0)
        self.assertFalse(stats["noop"])
        self.assertNotIn("DELETE FROM rainy_day_lookup;", sql)
        self.assertIn("INSERT OR REPLACE INTO rainy_day_lookup", sql)
        lookup_sql = sql.split("INSERT OR REPLACE INTO rainy_day_lookup", 1)[1].split(
            "INSERT OR REPLACE INTO pipeline_meta", 1
        )[0]
        self.assertIn("('2026-09-01'", lookup_sql)
        self.assertNotIn("('2026-08-31'", lookup_sql)
        self.assertIn("INSERT OR REPLACE INTO pipeline_meta", sql)
        self.assertIn("2026-09-01", sql[sql.index("pipeline_meta") :])
        self.assertEqual(stats["coverage"]["rows"], 2)
        self.assertEqual(stats["coverage"]["max_date"], "2026-09-01")

    def test_delta_noop_does_not_touch_d1(self):
        df = _frame(_row("2026-08-31", "Wan Chai", 0.0))
        sql, stats = render_delta_seed(df, df.copy())
        self.assertTrue(stats["noop"])
        self.assertEqual(stats["upserts"], 0)
        self.assertEqual(stats["deletes"], 0)
        self.assertNotIn("INSERT", sql)
        self.assertNotIn("DELETE", sql)

    def test_delta_deletes_removed_pks_only(self):
        existing = _frame(
            _row("2026-08-31", "Wan Chai", 0.0),
            _row("2026-08-31", "Islands", 0.0),
        )
        incoming = _frame(_row("2026-08-31", "Wan Chai", 0.0))
        sql, stats = render_delta_seed(incoming, existing)
        self.assertEqual(stats["deletes"], 1)
        self.assertIn("DELETE FROM rainy_day_lookup WHERE (date, district_en) IN", sql)
        self.assertIn("'Islands'", sql)
        self.assertNotIn("DELETE FROM rainy_day_lookup;", sql)

    def test_load_existing_json_reads_wrangler_execute_payload(self):
        payload = [
            {
                "results": [
                    _row("2026-08-31", "Wan Chai", 0),
                    _row("2026-08-31", "Islands", 0),
                ],
                "success": True,
            }
        ]
        df = load_existing_json(json.dumps(payload))
        self.assertEqual(len(df), 2)
        self.assertEqual(set(df["district_en"]), {"Wan Chai", "Islands"})

    def test_load_existing_json_skips_wrangler_log_prefix(self):
        row = _row("2026-08-31", "Wan Chai", 0)
        text = "Attempting to login via OAuth...\n" + json.dumps([{"results": [row], "success": True}])
        df = load_existing_json(text)
        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]["date"], "2026-08-31")


if __name__ == "__main__":
    unittest.main()
