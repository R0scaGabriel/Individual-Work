from __future__ import annotations

from copy import deepcopy
from statistics import mean
from time import time
from typing import Any

import requests

from .mock_data_service import mock_flood, mock_weather


FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
FLOOD_URL = "https://flood-api.open-meteo.com/v1/flood"
_CACHE_TTL_SECONDS = 600
_WEATHER_CACHE: dict[tuple[float, float, bool], tuple[float, dict[str, Any]]] = {}
_FLOOD_CACHE: dict[tuple[float, float, bool], tuple[float, dict[str, Any]]] = {}


def fetch_weather(lat: float, lon: float, allow_mock: bool = True) -> dict[str, Any]:
    cache_key = (round(float(lat), 3), round(float(lon), 3), bool(allow_mock))
    cached = _read_cache(_WEATHER_CACHE, cache_key)
    if cached is not None:
        return cached

    current_variables = [
        "temperature_2m",
        "relative_humidity_2m",
        "apparent_temperature",
        "precipitation",
        "rain",
        "snowfall",
        "wind_speed_10m",
        "wind_gusts_10m",
        "snow_depth",
        "freezing_level_height",
        "soil_moisture_0_to_1cm",
        "soil_moisture_1_to_3cm",
        "soil_moisture_3_to_9cm",
        "soil_moisture_9_to_27cm",
        "vapor_pressure_deficit",
        "et0_fao_evapotranspiration",
    ]
    daily_variables = [
        "temperature_2m_max",
        "temperature_2m_min",
        "apparent_temperature_max",
        "apparent_temperature_min",
        "precipitation_sum",
        "rain_sum",
        "snowfall_sum",
        "wind_speed_10m_max",
        "wind_gusts_10m_max",
        "et0_fao_evapotranspiration",
    ]
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": ",".join(current_variables),
        "daily": ",".join(daily_variables),
        "past_days": 30,
        "forecast_days": 7,
        "timezone": "auto",
    }
    try:
        result = _fetch_weather_payload(params, lat, lon, source="open-meteo")
        _write_cache(_WEATHER_CACHE, cache_key, result)
        return deepcopy(result)
    except Exception as primary_error:
        try:
            core_params = {
                **params,
                "current": ",".join(
                    [
                        "temperature_2m",
                        "relative_humidity_2m",
                        "apparent_temperature",
                        "precipitation",
                        "rain",
                        "snowfall",
                        "wind_speed_10m",
                        "wind_gusts_10m",
                    ]
                ),
                "daily": ",".join(
                    [
                        "temperature_2m_max",
                        "temperature_2m_min",
                        "apparent_temperature_max",
                        "apparent_temperature_min",
                        "precipitation_sum",
                        "rain_sum",
                        "snowfall_sum",
                        "wind_speed_10m_max",
                        "wind_gusts_10m_max",
                    ]
                ),
            }
            result = _fetch_weather_payload(core_params, lat, lon, source="open-meteo-core")
            result["note"] = f"Expanded Open-Meteo request failed, so the backend used core weather variables: {primary_error}"
            _write_cache(_WEATHER_CACHE, cache_key, result)
            return deepcopy(result)
        except Exception as error:
            if allow_mock:
                result = mock_weather(lat, lon)
                _write_cache(_WEATHER_CACHE, cache_key, result)
                return deepcopy(result)
            return {
                "source": "unavailable",
                "error": f"Open-Meteo weather request failed: {error}",
                "latitude": lat,
                "longitude": lon,
                "current": {},
                "daily": [],
            }


def _fetch_weather_payload(params: dict[str, Any], lat: float, lon: float, source: str) -> dict[str, Any]:
    response = requests.get(FORECAST_URL, params=params, timeout=12)
    response.raise_for_status()
    data = response.json()
    current = data.get("current") or {}
    daily = data.get("daily") or {}
    normalized_daily = []
    times = daily.get("time", [])
    for index, day in enumerate(times):
        t_max = _at(daily.get("temperature_2m_max"), index, current.get("temperature_2m", 0))
        t_min = _at(daily.get("temperature_2m_min"), index, t_max)
        normalized_daily.append(
            {
                "date": day,
                "temperature": round(mean([t_max, t_min]), 1),
                "temperature_max": t_max,
                "temperature_min": t_min,
                "apparent_temperature_max": _at(daily.get("apparent_temperature_max"), index, current.get("apparent_temperature", t_max)),
                "apparent_temperature_min": _at(daily.get("apparent_temperature_min"), index, current.get("apparent_temperature", t_min)),
                "precipitation": _at(daily.get("precipitation_sum"), index, 0),
                "rain": _at(daily.get("rain_sum"), index, 0),
                "snowfall": _at(daily.get("snowfall_sum"), index, 0),
                "humidity": current.get("relative_humidity_2m", 50),
                "wind_speed": _at(daily.get("wind_speed_10m_max"), index, current.get("wind_speed_10m", 0)),
                "wind_gusts": _at(daily.get("wind_gusts_10m_max"), index, current.get("wind_gusts_10m", 0)),
                "et0": _at(daily.get("et0_fao_evapotranspiration"), index, current.get("et0_fao_evapotranspiration", 0)),
            }
        )

    current.setdefault("snow_depth", 0)
    current.setdefault("snowfall", 0)
    current.setdefault("wind_gusts_10m", current.get("wind_speed_10m", 0))
    current.setdefault("freezing_level_height", None)
    current.setdefault("vapor_pressure_deficit", None)
    current.setdefault("et0_fao_evapotranspiration", None)
    current["recent_snowfall"] = _estimate_recent_snowfall(current, daily)
    return {
        "source": source,
        "latitude": data.get("latitude", lat),
        "longitude": data.get("longitude", lon),
        "current": current,
        "daily": normalized_daily,
    }


def fetch_flood(lat: float, lon: float, allow_mock: bool = True) -> dict[str, Any]:
    cache_key = (round(float(lat), 3), round(float(lon), 3), bool(allow_mock))
    cached = _read_cache(_FLOOD_CACHE, cache_key)
    if cached is not None:
        return cached

    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": ",".join(
            [
                "river_discharge",
                "river_discharge_mean",
                "river_discharge_median",
                "river_discharge_max",
                "river_discharge_min",
                "river_discharge_p25",
                "river_discharge_p75",
            ]
        ),
        "past_days": 30,
        "forecast_days": 30,
        "cell_selection": "land",
    }
    try:
        response = requests.get(FLOOD_URL, params=params, timeout=12)
        response.raise_for_status()
        data = response.json()
        data["source"] = "open-meteo-flood"
        _write_cache(_FLOOD_CACHE, cache_key, data)
        return deepcopy(data)
    except Exception as error:
        if allow_mock:
            result = mock_flood(lat, lon)
            _write_cache(_FLOOD_CACHE, cache_key, result)
            return deepcopy(result)
        return {
            "source": "unavailable",
            "error": f"Open-Meteo Flood request failed: {error}",
            "daily": {"time": [], "river_discharge": []},
        }


def _read_cache(
    cache: dict[tuple[float, float, bool], tuple[float, dict[str, Any]]],
    key: tuple[float, float, bool],
) -> dict[str, Any] | None:
    cached = cache.get(key)
    if not cached:
        return None
    timestamp, value = cached
    if time() - timestamp > _CACHE_TTL_SECONDS:
        cache.pop(key, None)
        return None
    return deepcopy(value)


def _write_cache(
    cache: dict[tuple[float, float, bool], tuple[float, dict[str, Any]]],
    key: tuple[float, float, bool],
    value: dict[str, Any],
) -> None:
    if len(cache) > 512:
        cache.clear()
    cache[key] = (time(), deepcopy(value))


def _at(values: list[Any] | None, index: int, default: float) -> float:
    if not values or index >= len(values) or values[index] is None:
        return float(default or 0)
    return float(values[index])


def _estimate_recent_snowfall(current: dict[str, Any], daily: dict[str, Any]) -> float:
    snow_depth = float(current.get("snow_depth") or 0)
    precipitation_values = daily.get("precipitation_sum") or []
    recent_precipitation = sum(float(value or 0) for value in precipitation_values[:2])
    if snow_depth <= 0:
        return 0
    return min(80, snow_depth * 0.15 + recent_precipitation * 0.4)
