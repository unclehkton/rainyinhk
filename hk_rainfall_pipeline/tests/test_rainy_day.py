#!/usr/bin/env python3
"""Contract tests for the district rainy-day lookup."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rainy_day import canonical_district, check_rainy  # noqa: E402


class CanonicalDistrictTests(unittest.TestCase):
    def test_english_and_chinese_aliases(self):
        self.assertEqual(canonical_district("Wan Chai"), "Wan Chai")
        self.assertEqual(canonical_district("wanchai"), "Wan Chai")
        self.assertEqual(canonical_district("灣仔區"), "Wan Chai")
        self.assertEqual(canonical_district("Kwun Tong"), "Kwun Tong")
        self.assertEqual(canonical_district("觀塘區"), "Kwun Tong")
        self.assertEqual(canonical_district("Southern"), "Southern")
        self.assertEqual(canonical_district("南區"), "Southern")


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

    def test_missing_date_is_unknown(self):
        row = check_rainy("1999-01-01", "Wan Chai")
        self.assertFalse(row["found"])
        self.assertIsNone(row["is_rainy"])
        self.assertIsNone(row["prev_is_rainy"])
        self.assertIsNone(row["two_day_rainy"])
        self.assertEqual(row["reason"], "no_row")

    def test_missing_hko_values_are_not_dry(self):
        row = check_rainy("2026-08-31", "Wan Chai")
        self.assertTrue(row["found"])
        self.assertFalse(row["data_ok"])
        self.assertIsNone(row["rainfall_mm"])
        self.assertIsNone(row["is_rainy"])
        self.assertIsNone(row["two_day_rainy"])


if __name__ == "__main__":
    unittest.main()
