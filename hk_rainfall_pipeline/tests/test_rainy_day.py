#!/usr/bin/env python3
"""Contract tests for the district rainy-day lookup."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import rainy_day  # noqa: E402
from rainy_day import canonical_district, check_rainy  # noqa: E402
from update_rainfall import build_lookup  # noqa: E402


class CanonicalDistrictTests(unittest.TestCase):
    def test_english_and_chinese_aliases(self):
        self.assertEqual(canonical_district("Wan Chai"), "Wan Chai")
        self.assertEqual(canonical_district("wanchai"), "Wan Chai")
        self.assertEqual(canonical_district("灣仔區"), "Wan Chai")
        self.assertEqual(canonical_district("Kwun Tong"), "Kwun Tong")
        self.assertEqual(canonical_district("觀塘區"), "Kwun Tong")
        self.assertEqual(canonical_district("Southern"), "Southern")
        self.assertEqual(canonical_district("南區"), "Southern")
        self.assertEqual(canonical_district("Lantau Island"), "Lantau Island")
        self.assertEqual(canonical_district("lantau"), "Lantau Island")
        self.assertEqual(canonical_district("大嶼山"), "Lantau Island")
        self.assertEqual(canonical_district("Islands"), "Islands")
        self.assertEqual(canonical_district("離島區"), "Islands")


class LookupContractTests(unittest.TestCase):
    def test_wan_chai_two_day_rainy(self):
        row = check_rainy("2024-04-20", "Wan Chai")
        self.assertTrue(row["found"])
        self.assertEqual(row["district_en"], "Wan Chai")
        self.assertEqual(row["rainfall_mm"], 21.0)
        self.assertEqual(row["prev_rainfall_mm"], 0.5)
        self.assertTrue(row["data_ok"])
        self.assertTrue(row["prev_data_ok"])
        self.assertTrue(row["is_rainy"])
        self.assertTrue(row["prev_is_rainy"])
        self.assertTrue(row["two_day_rainy"])
        self.assertEqual(row["assignment"], "reference_station")
        self.assertEqual(row["source_station_codes"], "VP1")

    def test_chinese_alias_resolves(self):
        row = check_rainy("2024-04-20", "灣仔區")
        self.assertTrue(row["found"])
        self.assertEqual(row["district_en"], "Wan Chai")
        self.assertTrue(row["two_day_rainy"])

    def test_kwun_tong_uses_kai_tak(self):
        row = check_rainy("2024-04-20", "Kwun Tong")
        self.assertTrue(row["found"])
        self.assertEqual(row["source_station_codes"], "SE")
        self.assertEqual(row["assignment"], "reference_station")

    def test_southern_uses_the_peak(self):
        row = check_rainy("2024-04-20", "Southern")
        self.assertTrue(row["found"])
        self.assertEqual(row["source_station_codes"], "VP1")
        self.assertEqual(row["assignment"], "reference_station")

    def _codes(self, row):
        return {c.strip() for c in str(row["source_station_codes"]).split(",") if c.strip()}

    def test_lantau_uses_airport(self):
        row = check_rainy("2024-04-20", "Lantau Island")
        self.assertTrue(row["found"])
        self.assertEqual(self._codes(row), {"HKA"})
        self.assertEqual(row["assignment"], "located_in_district")

    def test_other_islands_exclude_airport(self):
        row = check_rainy("2024-04-20", "Islands")
        self.assertTrue(row["found"])
        self.assertEqual(self._codes(row), {"CCH", "PEN", "WGL"})
        self.assertNotIn("HKA", self._codes(row))

    def test_missing_date_is_unknown(self):
        row = check_rainy("1999-01-01", "Wan Chai")
        self.assertFalse(row["found"])
        self.assertIsNone(row["is_rainy"])
        self.assertIsNone(row["prev_is_rainy"])
        self.assertIsNone(row["two_day_rainy"])
        self.assertEqual(row["reason"], "no_row")

    def test_missing_hko_values_are_not_dry(self):
        csv = Path(tempfile.mkdtemp()) / "rainy_day_lookup.csv"
        pd.DataFrame(
            [
                {
                    "date": "2099-01-15",
                    "district_en": "Wan Chai",
                    "district_zh": "灣仔區",
                    "assignment": "reference_station",
                    "source_station_codes": "VP1",
                    "n_stations": 1,
                    "n_stations_with_data": 0,
                    "n_nonzero_stations": 0,
                    "pct_nonzero_stations": pd.NA,
                    "rainfall_mm": pd.NA,
                    "wet_limit_mm": 0.2,
                    "data_ok": 0,
                    "is_rainy": pd.NA,
                    "prev_date": "2099-01-14",
                    "prev_rainfall_mm": pd.NA,
                    "prev_data_ok": 0,
                    "prev_is_rainy": pd.NA,
                    "two_day_rainy": pd.NA,
                    "refreshed_at_utc": "2026-01-01T00:00:00Z",
                }
            ]
        ).to_csv(csv, index=False)
        old_db, old_csv = rainy_day.DB_PATH, rainy_day.CSV_PATH
        rainy_day.DB_PATH = csv.with_name("missing.db")
        rainy_day.CSV_PATH = csv
        try:
            row = rainy_day.check_rainy("2099-01-15", "Wan Chai")
        finally:
            rainy_day.DB_PATH = old_db
            rainy_day.CSV_PATH = old_csv
        self.assertTrue(row["found"])
        self.assertFalse(row["data_ok"])
        self.assertIsNone(row["rainfall_mm"])
        self.assertIsNone(row["is_rainy"])
        self.assertIsNone(row["two_day_rainy"])


class BuildLookupNoDataTests(unittest.TestCase):
    def test_zero_stations_with_data_is_unknown_not_dry(self):
        dist = pd.DataFrame(
            [
                {
                    "date": pd.Timestamp("2099-01-15"),
                    "district_en": "Wan Chai",
                    "district_zh": "灣仔區",
                    "assignment": "reference_station",
                    "source_station_codes": "VP1",
                    "n_stations": 1,
                    "n_stations_with_data": 0,
                    "n_nonzero_stations": 0,
                    "rainfall_mm": pd.NA,
                }
            ]
        )
        out = build_lookup(dist).iloc[0]
        self.assertFalse(bool(out["data_ok"]))
        self.assertTrue(pd.isna(out["is_rainy"]))
        self.assertTrue(pd.isna(out["two_day_rainy"]))


if __name__ == "__main__":
    unittest.main()
