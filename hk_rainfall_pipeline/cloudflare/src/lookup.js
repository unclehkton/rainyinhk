/** District aliases and the programme contract for GET /rainy. */

export const DISTRICT_ALIASES = {
  "central and western": "Central and Western",
  central: "Central and Western",
  中西區: "Central and Western",
  "wan chai": "Wan Chai",
  wanchai: "Wan Chai",
  灣仔區: "Wan Chai",
  灣仔: "Wan Chai",
  eastern: "Eastern",
  東區: "Eastern",
  southern: "Southern",
  南區: "Southern",
  "yau tsim mong": "Yau Tsim Mong",
  ytm: "Yau Tsim Mong",
  油尖旺區: "Yau Tsim Mong",
  "sham shui po": "Sham Shui Po",
  深水埗區: "Sham Shui Po",
  "kowloon city": "Kowloon City",
  九龍城區: "Kowloon City",
  "wong tai sin": "Wong Tai Sin",
  黃大仙區: "Wong Tai Sin",
  "kwun tong": "Kwun Tong",
  觀塘區: "Kwun Tong",
  "tsuen wan": "Tsuen Wan",
  荃灣區: "Tsuen Wan",
  "tuen mun": "Tuen Mun",
  屯門區: "Tuen Mun",
  "yuen long": "Yuen Long",
  元朗區: "Yuen Long",
  north: "North",
  北區: "North",
  "tai po": "Tai Po",
  大埔區: "Tai Po",
  "sai kung": "Sai Kung",
  西貢區: "Sai Kung",
  "sha tin": "Sha Tin",
  shatin: "Sha Tin",
  沙田區: "Sha Tin",
  "kwai tsing": "Kwai Tsing",
  葵青區: "Kwai Tsing",
  islands: "Islands",
  離島區: "Islands",
};

export function canonicalDistrict(name) {
  const key = String(name ?? "").trim();
  return DISTRICT_ALIASES[key.toLowerCase()] ?? DISTRICT_ALIASES[key] ?? key;
}

export function isValidDate(value) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value ?? "")) return false;
  const d = new Date(`${value}T00:00:00Z`);
  return !Number.isNaN(d.getTime()) && d.toISOString().slice(0, 10) === value;
}

export function toBool(value) {
  if (value === null || value === undefined || value === "") return null;
  return Number(value) === 1;
}

export function verdict(row) {
  if (!row) return "UNKNOWN";
  const dataOk = toBool(row.data_ok);
  const prevOk = toBool(row.prev_data_ok);
  if (!dataOk || !prevOk) return "UNKNOWN";
  if (toBool(row.two_day_rainy)) return "RAINY_TWO_DAYS";
  if (toBool(row.is_rainy)) return "RAINY_TODAY_ONLY";
  return "NOT_RAINY";
}

export function shapeResponse(row, requestedDate, requestedDistrict) {
  const district = canonicalDistrict(requestedDistrict);
  if (!row) {
    return {
      found: false,
      date: requestedDate,
      district_en: district,
      is_rainy: null,
      prev_is_rainy: null,
      two_day_rainy: null,
      data_ok: null,
      prev_data_ok: null,
      verdict: "UNKNOWN",
      reason: "no_row",
    };
  }
  return {
    found: true,
    date: row.date,
    district_en: row.district_en,
    district_zh: row.district_zh,
    rainfall_mm: row.rainfall_mm,
    data_ok: toBool(row.data_ok),
    is_rainy: toBool(row.is_rainy),
    prev_date: row.prev_date,
    prev_rainfall_mm: row.prev_rainfall_mm,
    prev_data_ok: toBool(row.prev_data_ok),
    prev_is_rainy: toBool(row.prev_is_rainy),
    two_day_rainy: toBool(row.two_day_rainy),
    assignment: row.assignment,
    source_station_codes: row.source_station_codes,
    verdict: verdict(row),
  };
}
