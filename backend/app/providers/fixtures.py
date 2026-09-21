from datetime import datetime
from zoneinfo import ZoneInfo

from app.schemas.travel import POI, Coordinates, Place

TZ = ZoneInfo("Asia/Shanghai")
FIXED_NOW = datetime(2026, 10, 1, 8, tzinfo=TZ)
FIXTURE_VERSION = "synthetic-jiangnan-v1"
CITY_CODES = {"上海": "310100", "杭州": "330100", "南京": "320100", "苏州": "320500"}
STATIONS = {
    "上海": Place(
        id="sh-station",
        name="上海虹桥站",
        city="上海",
        coordinates=Coordinates(longitude=121.327, latitude=31.200),
    ),
    "杭州": Place(
        id="hz-station",
        name="杭州东站",
        city="杭州",
        coordinates=Coordinates(longitude=120.212, latitude=30.291),
    ),
    "南京": Place(
        id="nj-station",
        name="南京南站",
        city="南京",
        coordinates=Coordinates(longitude=118.797, latitude=31.969),
    ),
    "苏州": Place(
        id="sz-station",
        name="苏州站",
        city="苏州",
        coordinates=Coordinates(longitude=120.610, latitude=31.326),
    ),
}
# Geographic labels are illustrative; schedules, prices and opening hours are synthetic demo evidence.
POI_ROWS = {
    "杭州": [
        ("hz-west", "西湖", 120.149, 30.243, "outdoor", 0, ["自然", "夜景"]),
        ("hz-museum", "浙江省博物馆", 120.143, 30.251, "indoor", 0, ["历史"]),
        ("hz-hefang", "河坊街", 120.171, 30.235, "outdoor", 0, ["历史", "夜景"]),
        ("hz-silk", "中国丝绸博物馆", 120.150, 30.222, "indoor", 0, ["历史"]),
    ],
    "南京": [
        ("nj-wall", "明城墙", 118.790, 32.075, "outdoor", 3000, ["历史"]),
        ("nj-museum", "南京博物院", 118.825, 32.040, "indoor", 0, ["历史"]),
        ("nj-qinhuai", "秦淮河", 118.789, 32.020, "outdoor", 0, ["夜景"]),
        ("nj-history", "江宁织造博物馆", 118.792, 32.039, "indoor", 3000, ["历史"]),
    ],
    "苏州": [
        ("sz-garden", "拙政园", 120.629, 31.325, "outdoor", 8000, ["历史"]),
        ("sz-museum", "苏州博物馆", 120.627, 31.324, "indoor", 0, ["历史"]),
        ("sz-pingjiang", "平江路", 120.631, 31.316, "outdoor", 0, ["夜景"]),
        ("sz-silk", "苏州丝绸博物馆", 120.616, 31.327, "indoor", 0, ["历史"]),
    ],
    "上海": [
        ("sh-bund", "外滩", 121.490, 31.238, "outdoor", 0, ["夜景"]),
        ("sh-museum", "上海博物馆", 121.475, 31.228, "indoor", 0, ["历史"]),
        ("sh-yuyuan", "豫园", 121.492, 31.227, "outdoor", 4000, ["历史"]),
        ("sh-history", "上海市历史博物馆", 121.469, 31.232, "indoor", 0, ["历史"]),
    ],
}


def city_pois(city: str) -> list[POI]:
    from datetime import time

    return [
        POI(
            id=r[0],
            name=r[1],
            city=city,
            coordinates=Coordinates(longitude=r[2], latitude=r[3]),
            environment=r[4],
            ticket_price=r[5],
            tags=r[6],
            visit_minutes=90,
            opening_start=time(9),
            opening_end=time(21, 30) if "夜景" in r[6] else time(17),
            evidence_id=f"poi-{city}",
        )
        for r in POI_ROWS.get(city, [])
    ]
