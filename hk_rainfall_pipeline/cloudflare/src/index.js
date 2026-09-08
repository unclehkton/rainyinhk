import {
  apiKeyOk,
  canonicalDistrict,
  enquiryHttpStatus,
  extractApiKey,
  isKnownDistrict,
  parseDates,
  shapeEnquiry,
  shapeHealth,
} from "./lookup.js";

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, X-API-Key, Authorization",
};

function json(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", ...CORS },
  });
}

export default {
  async fetch(request, env) {
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: CORS });
    }
    if (request.method !== "GET") {
      return json({ error: "method_not_allowed" }, 405);
    }

    const url = new URL(request.url);
    if (url.pathname === "/") {
      return json({ ok: true, service: "hk-rainy-day" });
    }
    if (url.pathname === "/health") {
      try {
        const stats = await env.DB.prepare(
          `SELECT rows, districts, min_date, max_date, refreshed_at_utc
             FROM pipeline_meta
            WHERE id = 1`,
        ).first();
        const body = shapeHealth(stats);
        return json(body, body.ok ? 200 : 503);
      } catch {
        return json({ ok: false, error: "unhealthy", reasons: ["d1_error"] }, 503);
      }
    }
    if (url.pathname !== "/rainy") {
      return json({ error: "not_found" }, 404);
    }

    if (!apiKeyOk(extractApiKey(request), env.RAINY_API_KEY)) {
      return json({ error: "unauthorized", message: "missing or wrong API key" }, 401);
    }

    const districtRaw = url.searchParams.get("district") ?? "";
    if (!districtRaw) {
      return json({ error: "missing_params", need: ["district", "date or dates"] }, 400);
    }
    if (!isKnownDistrict(districtRaw)) {
      return json({ error: "unknown_district", district: districtRaw }, 400);
    }
    const parsed = parseDates(url.searchParams);
    if (parsed.error === "missing_dates") {
      return json({ error: "missing_params", need: ["district", "date or dates"] }, 400);
    }
    if (parsed.error === "invalid_date") {
      return json({ error: "invalid_date", date: parsed.date, message: "use YYYY-MM-DD" }, 400);
    }
    if (parsed.error) {
      return json({ error: parsed.error, max: parsed.max }, 400);
    }

    const district = canonicalDistrict(districtRaw);
    const bounds = await env.DB.prepare(
      `SELECT min_date, max_date FROM pipeline_meta WHERE id = 1`,
    ).first();
    const coverage = {
      min_date: bounds?.min_date ?? null,
      max_date: bounds?.max_date ?? null,
    };

    const placeholders = parsed.dates.map(() => "?").join(",");
    const result = await env.DB.prepare(
      `SELECT date, district_en, district_zh, rainfall_mm, data_ok, is_rainy
         FROM rainy_day_lookup
        WHERE district_en = ? AND date IN (${placeholders})`,
    )
      .bind(district, ...parsed.dates)
      .all();

    const body = shapeEnquiry(district, parsed.dates, result.results ?? [], coverage);
    const status = enquiryHttpStatus(body.days);
    if (status === 400) {
      return json({
        error: "out_of_range",
        message: "requested dates are outside the table",
        min_date: coverage.min_date,
        max_date: coverage.max_date,
        days: body.days,
      }, 400);
    }
    if (status === 500) {
      return json({
        error: "data_gap",
        message: "an in-range date is missing from the table",
        min_date: coverage.min_date,
        max_date: coverage.max_date,
        days: body.days,
      }, 500);
    }
    return json(body);
  },
};
