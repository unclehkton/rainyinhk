#!/usr/bin/env python3
"""Source Last-Modified / ETag fingerprint for scheduled skip-if-unchanged."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from update_rainfall import (  # noqa: E402
    collect_source_fingerprint,
    fingerprint_changed,
)


class FingerprintTests(unittest.TestCase):
    def test_collects_sample_station_urls(self):
        def headers(url: str):
            return {"last_modified": f"mod-{url[-10:]}", "etag": f'"{url[-4:]}"'}

        fp = collect_source_fingerprint(2026, header_fn=headers)
        self.assertEqual(fp["year"], 2026)
        self.assertEqual(
            set(fp["sources"]),
            {"HKO_ALL", "HKO_2026", "VP1_ALL", "VP1_2026", "SE_ALL", "SE_2026"},
        )
        self.assertTrue(fp["sources"]["HKO_ALL"]["url"].endswith("daily_HKO_RF_ALL.csv"))

    def test_no_store_is_changed_when_headers_present(self):
        current = {
            "sources": {"HKO_ALL": {"last_modified": "Tue, 03 Sep 2026", "etag": '"abc"'}}
        }
        self.assertTrue(fingerprint_changed(None, current))

    def test_same_headers_are_unchanged(self):
        fp = {"sources": {"HKO_ALL": {"last_modified": "A", "etag": "Y"}}}
        self.assertFalse(fingerprint_changed(fp, dict(fp)))

    def test_last_modified_change_is_changed(self):
        stored = {"sources": {"HKO_ALL": {"last_modified": "A", "etag": "Y"}}}
        current = {"sources": {"HKO_ALL": {"last_modified": "B", "etag": "Y"}}}
        self.assertTrue(fingerprint_changed(stored, current))

    def test_blank_headers_do_not_force_rebuild(self):
        stored = {"sources": {"HKO_ALL": {"last_modified": "A", "etag": "Y"}}}
        current = {"sources": {"HKO_ALL": {"last_modified": None, "etag": None}}}
        self.assertFalse(fingerprint_changed(stored, current))


if __name__ == "__main__":
    unittest.main()
