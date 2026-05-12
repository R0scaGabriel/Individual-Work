from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
from time import time
from typing import Any

import requests

from .mock_data_service import mock_earthquakes


USGS_RECENT_EARTHQUAKES_URL = (
    "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson"
)


def fetch_recent_earthquakes(limit: int = 30, allow_mock: bool = True) -> list[dict[str, Any]]:
    return deepcopy(_fetch_recent_earthquakes_cached(int(limit), bool(allow_mock), int(time() // 300)))


@lru_cache(maxsize=16)
def _fetch_recent_earthquakes_cached(limit: int, allow_mock: bool, cache_bucket: int) -> tuple[dict[str, Any], ...]:
    try:
        response = requests.get(USGS_RECENT_EARTHQUAKES_URL, timeout=8)
        response.raise_for_status()
        features = response.json().get("features", [])
        earthquakes = []
        for feature in features[:limit]:
            properties = feature.get("properties") or {}
            coordinates = (feature.get("geometry") or {}).get("coordinates") or [0, 0, 0]
            earthquakes.append(
                {
                    "id": feature.get("id"),
                    "place": properties.get("place") or "Unknown location",
                    "magnitude": properties.get("mag") or 0,
                    "depth": coordinates[2] if len(coordinates) > 2 else 0,
                    "lat": coordinates[1] if len(coordinates) > 1 else 0,
                    "lon": coordinates[0] if coordinates else 0,
                    "time": properties.get("time"),
                    "url": properties.get("url"),
                    "source": "usgs",
                }
            )
        return tuple(earthquakes or (mock_earthquakes() if allow_mock else []))
    except Exception:
        return tuple(mock_earthquakes() if allow_mock else [])
