from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import math
from typing import Any


DATA_DIR = Path(__file__).resolve().parent.parent / "data"
LOCATIONS_FILE = DATA_DIR / "sample_locations.json"


SUPPORTED_DISASTERS = [
    {"id": "flood", "label": "Flood"},
    {"id": "earthquake", "label": "Earthquake"},
    {"id": "wildfire", "label": "Wildfire"},
    {"id": "drought", "label": "Drought"},
    {"id": "heatwave", "label": "Heat Wave"},
    {"id": "landslide", "label": "Landslide"},
    {"id": "avalanche", "label": "Avalanche"},
]


def get_locations() -> list[dict[str, Any]]:
    with LOCATIONS_FILE.open("r", encoding="utf-8") as file:
        return json.load(file)


def find_nearest_location(lat: float, lon: float) -> dict[str, Any]:
    locations = get_locations()
    return min(
        locations,
        key=lambda item: (item["lat"] - lat) ** 2 + (item["lon"] - lon) ** 2,
    )


def mock_weather(lat: float, lon: float) -> dict[str, Any]:
    location = find_nearest_location(lat, lon)
    profiles = {
        "md-moldova": (28, 7, 52, 14, 0, 31),
        "ro-romania": (29, 10, 50, 12, 8, 33),
        "it-italy": (31, 4, 46, 13, 4, 36),
        "jp-japan": (29, 14, 68, 18, 15, 33),
        "np-nepal": (25, 18, 60, 10, 38, 29),
        "at-austria": (18, 12, 72, 9, 42, 21),
        "gr-greece": (33, 3, 42, 18, 0, 38),
        "tr-turkey": (31, 5, 46, 17, 4, 35),
        "es-spain": (34, 3, 38, 19, 0, 39),
        "fr-france": (27, 7, 54, 15, 6, 30),
        "de-germany": (25, 8, 58, 14, 3, 28),
        "pl-poland": (24, 8, 60, 13, 4, 27),
        "ua-ukraine": (27, 6, 50, 16, 3, 30),
        "us-california": (35, 2, 32, 24, 0, 41),
    }
    temperature, precipitation, humidity, wind, snow_depth, apparent = profiles.get(
        location["id"], (24, 6, 55, 12, 0, 26)
    )
    now = datetime.now(timezone.utc)
    historical = []
    for index in range(30):
        angle = index / 29 * math.pi
        historical.append(
            {
                "date": (now - timedelta(days=29 - index)).date().isoformat(),
                "temperature": round(temperature - 4 + math.sin(angle) * 6, 1),
                "precipitation": round(max(0, precipitation * (0.25 + math.cos(angle) ** 2)), 1),
                "humidity": round(min(100, max(15, humidity + math.cos(angle) * 12)), 1),
                "wind_speed": round(max(1, wind + math.sin(angle * 1.4) * 5), 1),
            }
        )

    return {
        "source": "mock",
        "location_id": location["id"],
        "location_name": location["name"],
        "latitude": lat,
        "longitude": lon,
        "current": {
            "temperature_2m": temperature,
            "apparent_temperature": apparent,
            "relative_humidity_2m": humidity,
            "precipitation": precipitation,
            "wind_speed_10m": wind,
            "snow_depth": snow_depth,
            "recent_snowfall": max(0, snow_depth * 0.22),
        },
        "daily": historical,
    }


def mock_flood(lat: float, lon: float) -> dict[str, Any]:
    location = find_nearest_location(lat, lon)
    discharge = {
        "md-moldova": 62,
        "ro-romania": 78,
        "it-italy": 44,
        "jp-japan": 86,
        "np-nepal": 72,
        "at-austria": 68,
        "gr-greece": 38,
        "tr-turkey": 55,
        "es-spain": 42,
        "fr-france": 64,
        "de-germany": 70,
        "pl-poland": 58,
        "ua-ukraine": 66,
        "us-california": 54,
    }.get(location["id"], 52)
    today = datetime.now(timezone.utc).date()
    return {
        "source": "mock",
        "daily": {
            "time": [(today + timedelta(days=i)).isoformat() for i in range(7)],
            "river_discharge": [round(discharge * (0.85 + 0.05 * i), 1) for i in range(7)],
        },
    }


def mock_earthquakes() -> list[dict[str, Any]]:
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    return [
        {
            "id": "mock-japan-001",
            "place": "Near Tokyo, Japan",
            "magnitude": 5.7,
            "depth": 38.0,
            "lat": 35.9,
            "lon": 140.3,
            "time": now_ms - 2 * 60 * 60 * 1000,
            "source": "mock",
        },
        {
            "id": "mock-california-001",
            "place": "Central California, USA",
            "magnitude": 4.6,
            "depth": 12.0,
            "lat": 36.3,
            "lon": -120.1,
            "time": now_ms - 5 * 60 * 60 * 1000,
            "source": "mock",
        },
        {
            "id": "mock-nepal-001",
            "place": "Himalayan region near Kathmandu",
            "magnitude": 5.2,
            "depth": 24.0,
            "lat": 27.9,
            "lon": 85.7,
            "time": now_ms - 10 * 60 * 60 * 1000,
            "source": "mock",
        },
    ]


def mock_fire_detections(lat: float, lon: float) -> list[dict[str, Any]]:
    location = find_nearest_location(lat, lon)
    active = {
        "us-california": 2,
        "it-italy": 1,
        "gr-greece": 1,
        "tr-turkey": 1,
        "es-spain": 1,
    }.get(location["id"], 0)
    return [
        {
            "id": f"mock-fire-{location['id']}-{index}",
            "lat": lat + 0.12 * (index + 1),
            "lon": lon - 0.1 * (index + 1),
            "confidence": 65 + index * 8,
            "source": "mock",
        }
        for index in range(active)
    ]
