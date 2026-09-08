import assert from "node:assert/strict";
import { describe, it } from "node:test";
import worker from "../src/index.js";

function mockEnv({ first = null, all = [], apiKey = "secret", fail = false } = {}) {
  const sqls = [];
  return {
    RAINY_API_KEY: apiKey,
    sqls,
    DB: {
      prepare(sql) {
        sqls.push(sql);
        if (fail) {
          return {
            bind() {
              return this;
            },
            async first() {
              throw new Error("d1 down");
            },
            async all() {
              throw new Error("d1 down");
            },
          };
        }
        return {
          bind() {
            return this;
          },
          async first() {
            return first;
          },
          async all() {
            return { results: all };
          },
        };
      },
    },
  };
}

async function get(path, env, headers = {}) {
  return worker.fetch(new Request(`https://hk-rainy-day.test${path}`, { headers }), env);
}

describe("worker", () => {
  it("keeps / as a cheap liveness probe", async () => {
    const res = await get("/", mockEnv({ fail: true }));
    assert.equal(res.status, 200);
    assert.deepEqual(await res.json(), { ok: true, service: "hk-rainy-day" });
  });

  it("health-checks D1 and fails when the table is empty", async () => {
    const env = mockEnv({
      first: {
        rows: 0,
        districts: 0,
        min_date: null,
        max_date: null,
        refreshed_at_utc: null,
      },
    });
    const res = await get("/health", env);
    assert.equal(res.status, 503);
    const body = await res.json();
    assert.equal(body.ok, false);
    assert.ok(body.reasons.includes("empty"));
    assert.match(env.sqls[0], /pipeline_meta/);
    assert.doesNotMatch(env.sqls[0], /rainy_day_lookup/);
  });

  it("rejects query-string API keys", async () => {
    const res = await get("/rainy?key=secret&district=Wan%20Chai&date=2024-04-20", mockEnv());
    assert.equal(res.status, 401);
    assert.equal((await res.json()).error, "unauthorized");
  });

  it("accepts Authorization Bearer and returns a rainy day", async () => {
    const env = mockEnv({
      first: { min_date: "2024-01-01", max_date: "2026-08-31" },
      all: [
        {
          date: "2024-04-20",
          district_en: "Wan Chai",
          district_zh: "灣仔區",
          rainfall_mm: 21,
          data_ok: 1,
          is_rainy: 1,
        },
      ],
    });
    const res = await get("/rainy?district=Wan%20Chai&date=2024-04-20", env, {
      Authorization: "Bearer secret",
    });
    assert.equal(res.status, 200);
    const body = await res.json();
    assert.equal(body.days[0].rainfall_mm, 21);
    assert.equal(body.days[0].error, null);
    assert.match(env.sqls[0], /pipeline_meta/);
    assert.match(env.sqls[1], /rainy_day_lookup/);
    assert.doesNotMatch(env.sqls[0], /MIN\(date\)/);
  });

  it("returns 500 data_gap for a missing in-range row", async () => {
    const env = mockEnv({
      first: { min_date: "2024-01-01", max_date: "2026-08-31" },
      all: [],
    });
    const res = await get("/rainy?district=Wan%20Chai&date=2025-06-10", env, {
      "X-API-Key": "secret",
    });
    assert.equal(res.status, 500);
    const body = await res.json();
    assert.equal(body.error, "data_gap");
    assert.equal(body.days[0].error, "data_gap");
  });
});
