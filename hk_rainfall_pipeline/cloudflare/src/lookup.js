/** District aliases and the simplified rainy-day enquiry. */

export const MAX_DATES = 62;

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
  "lantau island": "Lantau Island",
  lantau: "Lantau Island",
  大嶼山: "Lantau Island",
  大嶼山區: "Lantau Island",
};

export const DISTRICT_ZH = {
  "Central and Western": "中西區",
  "Wan Chai": "灣仔區",
  Eastern: "東區",
  Southern: "南區",
  "Yau Tsim Mong": "油尖旺區",
  "Sham Shui Po": "深水埗區",
  "Kowloon City": "九龍城區",
  "Wong Tai Sin": "黃大仙區",
  "Kwun Tong": "觀塘區",
  "Tsuen Wan": "荃灣區",
  "Tuen Mun": "屯門區",
  "Yuen Long": "元朗區",
  North: "北區",
  "Tai Po": "大埔區",
  "Sai Kung": "西貢區",
  "Sha Tin": "沙田區",
  "Kwai Tsing": "葵青區",
  Islands: "離島區",
  "Lantau Island": "大嶼山",
};

export function canonicalDistrict(name) {
  const key = String(name ?? "").trim();
  return DISTRICT_ALIASES[key.toLowerCase()] ?? DISTRICT_ALIASES[key] ?? key;
}

export function isKnownDistrict(name) {
  return Object.prototype.hasOwnProperty.call(DISTRICT_ZH, canonicalDistrict(name));
}

export function extractApiKey(request) {
  const url = new URL(request.url);
  const fromQuery = url.searchParams.get("key");
  if (fromQuery && fromQuery.trim()) return fromQuery.trim();
  const fromHeader = request.headers.get("X-API-Key") ?? request.headers.get("x-api-key");
  if (fromHeader && fromHeader.trim()) return fromHeader.trim();
  const auth = request.headers.get("Authorization") ?? "";
  if (auth.toLowerCase().startsWith("bearer ")) return auth.slice(7).trim();
  return "";
}

export function apiKeyOk(provided, expected) {
  if (!expected || !provided) return false;
  return provided === expected;
}

export function isValidDate(value) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value ?? "")) return false;
  const d = new Date(`${value}T00:00:00Z`);
  return !Number.isNaN(d.getTime()) && d.toISOString().slice(0, 10) === value;
}

export function parseDates(searchParams) {
  const raw = [];
  for (const value of searchParams.getAll("dates")) {
    raw.push(...String(value).split(/[,\s]+/));
  }
  for (const value of searchParams.getAll("date")) raw.push(value);
  const dates = [];
  const seen = new Set();
  for (const item of raw) {
    const date = String(item).trim();
    if (!date) continue;
    if (!isValidDate(date)) return { error: "invalid_date", date };
    if (seen.has(date)) continue;
    seen.add(date);
    dates.push(date);
  }
  if (!dates.length) return { error: "missing_dates" };
  if (dates.length > MAX_DATES) return { error: "too_many_dates", max: MAX_DATES };
  return { dates };
}

export function toBool(value) {
  if (value === null || value === undefined || value === "") return null;
  return Number(value) === 1;
}

export function shapeDay(row, date, coverage = {}) {
  const minDate = coverage.min_date ?? null;
  const maxDate = coverage.max_date ?? null;
  if (minDate && maxDate && (date < minDate || date > maxDate)) {
    return { date, rainfall_mm: null, is_rainy: null, error: "out_of_range" };
  }
  if (!row) {
    return { date, rainfall_mm: null, is_rainy: null, error: "out_of_range" };
  }
  if (!toBool(row.data_ok)) {
    return { date, rainfall_mm: null, is_rainy: null, error: "no_data" };
  }
  const mm = row.rainfall_mm;
  return {
    date,
    rainfall_mm: mm === null || mm === undefined || mm === "" ? null : Number(mm),
    is_rainy: toBool(row.is_rainy),
    error: null,
  };
}

export function shapeEnquiry(districtRaw, dates, rows, coverage = {}) {
  const district = canonicalDistrict(districtRaw);
  const byDate = new Map((rows ?? []).map((row) => [row.date, row]));
  return {
    district,
    district_zh: DISTRICT_ZH[district] ?? rows?.[0]?.district_zh ?? null,
    coverage: {
      min_date: coverage.min_date ?? null,
      max_date: coverage.max_date ?? null,
    },
    days: dates.map((date) => shapeDay(byDate.get(date) ?? null, date, coverage)),
  };
}

export function enquiryHttpStatus(days) {
  if (!days?.length) return 400;
  if (days.every((day) => day.error === "out_of_range")) return 400;
  return 200;
}
