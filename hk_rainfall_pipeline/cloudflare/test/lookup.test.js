import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  canonicalDistrict,
  isValidDate,
  parseDates,
  shapeDay,
  shapeEnquiry,
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

describe("shapeDay", () => {
  it("returns mm and rainy when HKO published a value", () => {
    assert.deepEqual(
      shapeDay(
        { date: "2024-04-20", rainfall_mm: 21, data_ok: 1, is_rainy: 1 },
        "2024-04-20",
      ),
      { date: "2024-04-20", rainfall_mm: 21, is_rainy: true },
    );
  });
  it("returns nulls when the day is missing", () => {
    assert.deepEqual(shapeDay(null, "1999-01-01"), {
      date: "1999-01-01",
      rainfall_mm: null,
      is_rainy: null,
    });
  });
  it("returns nulls when HKO has not published (not dry)", () => {
    assert.deepEqual(
      shapeDay(
        { date: "2026-08-31", rainfall_mm: null, data_ok: 0, is_rainy: null },
        "2026-08-31",
      ),
      { date: "2026-08-31", rainfall_mm: null, is_rainy: null },
    );
  });
  it("returns 0 mm and not rainy for a dry published day", () => {
    assert.deepEqual(
      shapeDay(
        { date: "2024-01-02", rainfall_mm: 0, data_ok: 1, is_rainy: 0 },
        "2024-01-02",
      ),
      { date: "2024-01-02", rainfall_mm: 0, is_rainy: false },
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
    ]);
    assert.deepEqual(out, {
      district: "Wan Chai",
      district_zh: "灣仔區",
      days: [
        { date: "2024-04-20", rainfall_mm: 21, is_rainy: true },
        { date: "2024-04-19", rainfall_mm: 0.5, is_rainy: true },
      ],
    });
  });
});
