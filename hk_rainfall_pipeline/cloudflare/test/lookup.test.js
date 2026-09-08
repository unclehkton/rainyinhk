import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  canonicalDistrict,
  isValidDate,
  shapeResponse,
  verdict,
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

describe("verdict", () => {
  it("UNKNOWN when the row is missing", () => {
    assert.equal(verdict(null), "UNKNOWN");
  });
  it("UNKNOWN when today has no HKO value", () => {
    assert.equal(
      verdict({ data_ok: 0, prev_data_ok: 1, is_rainy: null, two_day_rainy: null }),
      "UNKNOWN",
    );
  });
  it("UNKNOWN when yesterday has no HKO value", () => {
    assert.equal(
      verdict({ data_ok: 1, prev_data_ok: null, is_rainy: 1, two_day_rainy: null }),
      "UNKNOWN",
    );
  });
  it("RAINY_TWO_DAYS only when both days are wet and both have data", () => {
    assert.equal(
      verdict({ data_ok: 1, prev_data_ok: 1, is_rainy: 1, two_day_rainy: 1 }),
      "RAINY_TWO_DAYS",
    );
  });
  it("RAINY_TODAY_ONLY when only today is wet", () => {
    assert.equal(
      verdict({ data_ok: 1, prev_data_ok: 1, is_rainy: 1, two_day_rainy: 0 }),
      "RAINY_TODAY_ONLY",
    );
  });
  it("NOT_RAINY when today is dry and both days have data", () => {
    assert.equal(
      verdict({ data_ok: 1, prev_data_ok: 1, is_rainy: 0, two_day_rainy: 0 }),
      "NOT_RAINY",
    );
  });
});

describe("shapeResponse", () => {
  it("marks a missing row unknown", () => {
    const out = shapeResponse(null, "2024-04-20", "灣仔區");
    assert.equal(out.found, false);
    assert.equal(out.district_en, "Wan Chai");
    assert.equal(out.verdict, "UNKNOWN");
    assert.equal(out.two_day_rainy, null);
  });

  it("exposes two_day_rainy for the known Wan Chai wet pair", () => {
    const out = shapeResponse(
      {
        date: "2024-04-20",
        district_en: "Wan Chai",
        district_zh: "灣仔區",
        rainfall_mm: 21,
        data_ok: 1,
        is_rainy: 1,
        prev_date: "2024-04-19",
        prev_rainfall_mm: 0.5,
        prev_data_ok: 1,
        prev_is_rainy: 1,
        two_day_rainy: 1,
        assignment: "reference_station",
        source_station_codes: "VP1",
      },
      "2024-04-20",
      "Wan Chai",
    );
    assert.equal(out.found, true);
    assert.equal(out.two_day_rainy, true);
    assert.equal(out.verdict, "RAINY_TWO_DAYS");
    assert.equal(out.assignment, "reference_station");
    assert.equal(out.source_station_codes, "VP1");
  });
});
