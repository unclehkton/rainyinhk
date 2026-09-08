import { canonicalDistrict, parseDates, shapeEnquiry } from "./lookup.js";

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

    const districtRaw = url.searchParams.get("district") ?? "";
    if (!districtRaw) {
      return json({ error: "missing_params", need: ["district", "date or dates"] }, 400);
    }
    const parsed = parseDates(url.searchParams);
    if (parsed.error === "missing_dates") {
      return json({ error: "missing_params", need: ["district", "date or dates"] }, 400);
    }
    if (parsed.error === "invalid_date") {
      return json({ error: "invalid_date", date: parsed.date }, 400);
    }
    if (parsed.error) {
      return json({ error: parsed.error, max: parsed.max }, 400);
    }

    const district = canonicalDistrict(districtRaw);
    const placeholders = parsed.dates.map(() => "?").join(",");
    const result = await env.DB.prepare(
      `SELECT date, district_en, district_zh, rainfall_mm, data_ok, is_rainy
         FROM rainy_day_lookup
        WHERE district_en = ? AND date IN (${placeholders})`,
    )
      .bind(district, ...parsed.dates)
      .all();

    return json(shapeEnquiry(district, parsed.dates, result.results ?? []));
  },
};
