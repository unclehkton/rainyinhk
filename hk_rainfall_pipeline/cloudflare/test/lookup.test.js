import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  EXPECTED_DISTRICTS,
  apiKeyOk,
  canonicalDistrict,
  enquiryHttpStatus,
  extractApiKey,
  isKnownDistrict,
  isValidDate,
  parseDates,
  shapeDay,
  shapeEnquiry,
  shapeHealth,
} from "../src/lookup.js";

describe("canonicalDistrict", () => {
  it("maps English and Chinese aliases", () => {
    assert.equal(canonicalDistrict("Wan Chai"), "Wan Chai");
    assert.equal(canonicalDistrict("wanchai"), "Wan Chai");
    assert.equal(canonicalDistrict("灣仔區"), "Wan Chai");
    assert.equal(canonicalDistrict("Kwun Tong"), "Kwun Tong");
    assert.equal(canonicalDistrict("觀塘區"), "Kwun Tong");
    assert.equal(canonicalDistrict("Southern"), "Southern");
    assert.equal(canonicalDistrict("南區"), "Southern");
    assert.equal(canonicalDistrict("Lantau Island"), "Lantau Island");
    assert.equal(canonicalDistrict("lantau"), "Lantau Island");
    assert.equal(canonicalDistrict("大嶼山"), "Lantau Island");
    assert.equal(canonicalDistrict("Islands"), "Islands");
    assert.equal(canonicalDistrict("離島區"), "Islands");
  });
});

describe("isValidDate", () => {
  it("accepts ISO calendar dates", () => {
    assert.equal(isValidDate("2024-04-20"), true);
  });
  it("rejects junk", () => {
    assert.equal(isValidDate("2024/04/20"), false);
    assert.equal(isValidDate("20-04-2024"), false);
    assert.equal(isValidDate(""), false);
  });
});

describe("parseDates", () => {
  it("accepts a single date=", () => {
    const q = new URLSearchParams("date=2024-04-20");
    assert.deepEqual(parseDates(q), { dates: ["2024-04-20"] });
  });
  it("accepts repeated date= and comma-separated dates=", () => {
    const q = new URLSearchParams("dates=2024-04-19,2024-04-20&date=2024-04-21");
    assert.deepEqual(parseDates(q), {
      dates: ["2024-04-19", "2024-04-20", "2024-04-21"],
    });
  });
  it("dedupes while keeping first-seen order", () => {
    const q = new URLSearchParams("dates=2024-04-20,2024-04-19,2024-04-20");
    assert.deepEqual(parseDates(q), { dates: ["2024-04-20", "2024-04-19"] });
  });
  it("rejects an invalid date", () => {
    const q = new URLSearchParams("dates=2024-04-20,nope");
    assert.equal(parseDates(q).error, "invalid_date");
    assert.equal(parseDates(q).date, "nope");
  });
  it("rejects a missing list", () => {
    assert.equal(parseDates(new URLSearchParams("district=Wan+Chai")).error, "missing_dates");
  });
});

describe("apiKey", () => {
  it("rejects missing or wrong keys", () => {
    assert.equal(apiKeyOk("", "secret"), false);
    assert.equal(apiKeyOk("nope", "secret"), false);
    assert.equal(apiKeyOk("secret", ""), false);
  });
  it("accepts the matching key", () => {
    assert.equal(apiKeyOk("secret", "secret"), true);
  });
  it("reads key from X-API-Key or Bearer, not the query string", () => {
    const q = new Request("https://x/rainy?key=from-query");
    assert.equal(extractApiKey(q), "");
    const h = new Request("https://x/rainy?key=from-query", {
      headers: { "X-API-Key": "from-header" },
    });
    assert.equal(extractApiKey(h), "from-header");
    const b = new Request("https://x/rainy", { headers: { Authorization: "Bearer from-bearer" } });
    assert.equal(extractApiKey(b), "from-bearer");
  });
});

describe("isKnownDistrict", () => {
  it("accepts canonical names and aliases", () => {
    assert.equal(isKnownDistrict("Wan Chai"), true);
    assert.equal(isKnownDistrict("灣仔區"), true);
    assert.equal(isKnownDistrict("Lantau Island"), true);
    assert.equal(isKnownDistrict("NotADistrict"), false);
  });
});

describe("shapeDay", () => {
  const range = { min_date: "2024-01-01", max_date: "2026-08-31" };
  it("returns mm and rainy when HKO published a value", () => {
    assert.deepEqual(
      shapeDay(
        { date: "2024-04-20", rainfall_mm: 21, data_ok: 1, is_rainy: 1 },
        "2024-04-20",
        range,
      ),
      { date: "2024-04-20", rainfall_mm: 21, is_rainy: true, error: null },
    );
  });
  it("marks dates outside coverage as out_of_range", () => {
    assert.deepEqual(shapeDay(null, "1999-01-01", range), {
      date: "1999-01-01",
      rainfall_mm: null,
      is_rainy: null,
      error: "out_of_range",
    });
    assert.deepEqual(shapeDay(null, "2030-01-01", range), {
      date: "2030-01-01",
      rainfall_mm: null,
      is_rainy: null,
      error: "out_of_range",
    });
  });
  it("marks unpublished HKO days as no_data, not dry", () => {
    assert.deepEqual(
      shapeDay(
        { date: "2026-08-15", rainfall_mm: null, data_ok: 0, is_rainy: null },
        "2026-08-15",
        range,
      ),
      { date: "2026-08-15", rainfall_mm: null, is_rainy: null, error: "no_data" },
    );
  });
  it("marks a missing in-range row as data_gap, not out_of_range", () => {
    assert.deepEqual(shapeDay(null, "2025-06-10", range), {
      date: "2025-06-10",
      rainfall_mm: null,
      is_rainy: null,
      error: "data_gap",
    });
  });
  it("returns 0 mm and not rainy for a dry published day", () => {
    assert.deepEqual(
      shapeDay(
        { date: "2024-01-02", rainfall_mm: 0, data_ok: 1, is_rainy: 0 },
        "2024-01-02",
        range,
      ),
      { date: "2024-01-02", rainfall_mm: 0, is_rainy: false, error: null },
    );
  });
});

describe("shapeEnquiry", () => {
  it("returns one district and one row per requested date", () => {
    const out = shapeEnquiry("灣仔區", ["2024-04-20", "2024-04-19"], [
      {
        date: "2024-04-20",
        district_en: "Wan Chai",
        district_zh: "灣仔區",
        rainfall_mm: 21,
        data_ok: 1,
        is_rainy: 1,
      },
      {
        date: "2024-04-19",
        district_en: "Wan Chai",
        district_zh: "灣仔區",
        rainfall_mm: 0.5,
        data_ok: 1,
        is_rainy: 1,
      },
    ], { min_date: "2024-01-01", max_date: "2026-08-31" });
    assert.deepEqual(out, {
      district: "Wan Chai",
      district_zh: "灣仔區",
      coverage: { min_date: "2024-01-01", max_date: "2026-08-31" },
      days: [
        { date: "2024-04-20", rainfall_mm: 21, is_rainy: true, error: null },
        { date: "2024-04-19", rainfall_mm: 0.5, is_rainy: true, error: null },
      ],
    });
  });
  it("uses HTTP 400 when every date is out of range", () => {
    const out = shapeEnquiry(
      "Wan Chai",
      ["1999-01-01", "1999-01-02"],
      [],
      { min_date: "2024-01-01", max_date: "2026-08-31" },
    );
    assert.equal(enquiryHttpStatus(out.days), 400);
    assert.equal(out.days[0].error, "out_of_range");
  });
  it("uses HTTP 500 when an in-range row is missing", () => {
    const out = shapeEnquiry(
      "Wan Chai",
      ["2025-06-10"],
      [],
      { min_date: "2024-01-01", max_date: "2026-08-31" },
    );
    assert.equal(out.days[0].error, "data_gap");
    assert.equal(enquiryHttpStatus(out.days), 500);
  });
});

describe("shapeHealth", () => {
  const now = new Date("2026-09-08T12:00:00Z");
  const good = {
    rows: 18506,
    districts: EXPECTED_DISTRICTS,
    min_date: "2024-01-01",
    max_date: "2026-08-31",
    refreshed_at_utc: "2026-09-08T08:48:53Z",
  };

  it("exposes 18 District Councils plus Lantau Island", () => {
    assert.equal(EXPECTED_DISTRICTS, 19);
  });

  it("is healthy for a complete recent grid", () => {
    assert.deepEqual(shapeHealth(good, now), {
      ok: true,
      rows: 18506,
      districts: 19,
      min_date: "2024-01-01",
      max_date: "2026-08-31",
      refreshed_at_utc: "2026-09-08T08:48:53Z",
    });
  });

  it("fails when the table is empty", () => {
    const out = shapeHealth(
      { rows: 0, districts: 0, min_date: null, max_date: null, refreshed_at_utc: null },
      now,
    );
    assert.equal(out.ok, false);
    assert.ok(out.reasons.includes("empty"));
  });

  it("fails when an in-range day is missing from the grid", () => {
    const out = shapeHealth({ ...good, rows: 18505 }, now);
    assert.equal(out.ok, false);
    assert.ok(out.reasons.includes("incomplete_grid"));
  });

  it("fails when max_date is more than 120 days old", () => {
    const out = shapeHealth({ ...good, max_date: "2026-01-01" }, now);
    assert.equal(out.ok, false);
    assert.ok(out.reasons.includes("stale"));
  });
});
