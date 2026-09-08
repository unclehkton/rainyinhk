"""Business rules and station directory for HK district rainy-day lookup."""

from __future__ import annotations

WET_LIMIT_MM = 0.2
START_YEAR = 2024
SOURCE_DATASET = "https://data.gov.hk/en-data/dataset/hk-hko-rss-daily-total-rainfall"
CSDI_ALL = "https://data.weather.gov.hk/weatherAPI/hko_data/csdi/dataset/daily_{code}_RF_ALL.csv"
CSDI_YEAR = "https://data.weather.gov.hk/weatherAPI/hko_data/csdi/dataset/daily_{code}_RF_{year}.csv"

DISTRICTS = [
    ("Central and Western", "中西區"),
    ("Wan Chai", "灣仔區"),
    ("Eastern", "東區"),
    ("Southern", "南區"),
    ("Yau Tsim Mong", "油尖旺區"),
    ("Sham Shui Po", "深水埗區"),
    ("Kowloon City", "九龍城區"),
    ("Wong Tai Sin", "黃大仙區"),
    ("Kwun Tong", "觀塘區"),
    ("Tsuen Wan", "荃灣區"),
    ("Tuen Mun", "屯門區"),
    ("Yuen Long", "元朗區"),
    ("North", "北區"),
    ("Tai Po", "大埔區"),
    ("Sai Kung", "西貢區"),
    ("Sha Tin", "沙田區"),
    ("Kwai Tsing", "葵青區"),
    ("Islands", "離島區"),
    ("Lantau Island", "大嶼山"),
]
DIST_ZH = {en: zh for en, zh in DISTRICTS}

# code, name_en, name_zh, district_en, lat_dd, lon_dd
STATIONS = [
    ("HKA", "Hong Kong International Airport", "香港國際機場", "Lantau Island", 22.309444, 113.921944),
    ("CCH", "Cheung Chau", "長洲", "Islands", 22.201111, 114.026667),
    ("HKO", "Hong Kong Observatory", "香港天文台", "Yau Tsim Mong", 22.301944, 114.174167),
    ("SE", "Kai Tak", "啟德", "Kowloon City", 22.309722, 114.213333),
    ("KSC", "Kau Sai Chau", "滘西洲", "Sai Kung", 22.370278, 114.312500),
    ("KP", "King's Park", "京士柏", "Yau Tsim Mong", 22.311944, 114.172778),
    ("LFS", "Lau Fau Shan", "流浮山", "Yuen Long", 22.468889, 113.983611),
    ("TYW", "Pak Tam Chung (Tsak Yue Wu)", "北潭涌（鯽魚湖）", "Sai Kung", 22.402778, 114.323056),
    ("PEN", "Peng Chau", "坪洲", "Islands", 22.291111, 114.043333),
    ("SHA", "Sha Tin", "沙田", "Sha Tin", 22.402500, 114.210000),
    ("SSP", "Sham Shui Po", "深水埗", "Sham Shui Po", 22.336111, 114.136944),
    ("SKW", "Shau Kei Wan", "筲箕灣", "Eastern", 22.281944, 114.236111),
    ("SEK", "Shek Kong", "石崗", "Yuen Long", 22.436389, 114.084722),
    ("SSH", "Sheung Shui", "上水", "North", 22.501944, 114.111111),
    ("TKL", "Ta Kwu Ling", "打鼓嶺", "North", 22.528611, 114.156667),
    ("PLC", "Tai Mei Tuk", "大美督", "Tai Po", 22.475278, 114.237500),
    ("TMS", "Tai Mo Shan", "大帽山", "Tsuen Wan", 22.410556, 114.124444),
    ("TC", "Tate's Cairn", "大老山", "Wong Tai Sin", 22.357778, 114.217778),
    ("VP1", "The Peak", "山頂", "Central and Western", 22.264167, 114.155000),
    ("JKB", "Tseung Kwan O", "將軍澳", "Sai Kung", 22.315833, 114.255556),
    ("CPH", "Ching Pak House (Tsing Yi)", "青衣（青柏樓）", "Kwai Tsing", 22.348056, 114.109167),
    ("TWN", "Tsuen Wan", "荃灣", "Tsuen Wan", 22.383611, 114.107778),
    ("TU1", "Tuen Mun Children and Juvenile Home", "屯門兒童及青少年院", "Tuen Mun", 22.385833, 113.964167),
    ("WGL", "Waglan Island", "橫瀾島", "Islands", 22.182222, 114.303333),
    ("WLP", "Wetland Park", "濕地公園", "Yuen Long", 22.466667, 114.008889),
]
STATION_BY_CODE = {s[0]: s for s in STATIONS}

# Districts with no site in the 25-station set use a nearby official station.
REFERENCE_STATIONS = {
    "Wan Chai": "VP1",
    "Southern": "VP1",
    "Kwun Tong": "SE",
}
