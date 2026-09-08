import { canonicalDistrict, isValidDate, shapeResponse } from "./lookup.js";

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
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
    if (url.pathname === "/" || url.pathname === "/health") {
      return json({ ok: true, service: "hk-rainy-day" });
    }
    if (url.pathname !== "/rainy") {
      return json({ error: "not_found" }, 404);
    }

    const date = url.searchParams.get("date") ?? "";
    const districtRaw = url.searchParams.get("district") ?? "";
    if (!date || !districtRaw) {
      return json({ error: "missing_params", need: ["date", "district"] }, 400);
    }
    if (!isValidDate(date)) {
      return json({ error: "invalid_date", date }, 400);
    }

    const district = canonicalDistrict(districtRaw);
    const row = await env.DB.prepare(
      `SELECT date, district_en, district_zh, assignment, source_station_codes,
              rainfall_mm, data_ok, is_rainy, prev_date, prev_rainfall_mm,
              prev_data_ok, prev_is_rainy, two_day_rainy
         FROM rainy_day_lookup
        WHERE district_en = ? AND date = ?
        LIMIT 1`,
    )
      .bind(district, date)
      .first();

    return json(shapeResponse(row, date, district));
  },
};
