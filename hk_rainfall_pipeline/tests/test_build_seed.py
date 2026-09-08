#!/usr/bin/env python3
"""Coverage row for the one-row D1 pipeline_meta table."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cloudflare"))

from build_seed import coverage_from_lookup  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
