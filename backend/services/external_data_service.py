from __future__ import annotations

import csv
from datetime import date, timedelta
from functools import lru_cache
import json
import math
import os
from statistics import mean
from typing import Any
from xml.etree import ElementTree

import requests

from .normalization import haversine


NASA_POWER_DAILY_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
FIRMS_AREA_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
USGS_EVENT_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"
WORLDPOP_STATS_URL = "https://api.worldpop.org/v1/services/stats"


ISO3_BY_LOCATION_ID = {
    "md-moldova": "MDA",
    "ro-romania": "ROU",
    "it-italy": "ITA",
    "jp-japan": "JPN",
    "np-nepal": "NPL",
    "at-austria": "AUT",
    "gr-greece": "GRC",
    "tr-turkey": "TUR",
    "es-spain": "ESP",
    "fr-france": "FRA",
    "de-germany": "DEU",
    "pt-portugal": "PRT",
    "gb-united-kingdom": "GBR",
    "ie-ireland": "IRL",
    "nl-netherlands": "NLD",
    "be-belgium": "BEL",
    "ch-switzerland": "CHE",
    "cz-czechia": "CZE",
    "hu-hungary": "HUN",
    "bg-bulgaria": "BGR",
    "hr-croatia": "HRV",
    "se-sweden": "SWE",
    "no-norway": "NOR",
    "pl-poland": "POL",
    "ua-ukraine": "UKR",
    "ca-canada": "CAN",
    "us-united-states": "USA",
    "mx-mexico": "MEX",
    "br-brazil": "BRA",
    "ar-argentina": "ARG",
    "cl-chile": "CHL",
    "co-colombia": "COL",
    "pe-peru": "PER",
}


def fetch_external_context(
    location: dict[str, Any],
    closest_earthquake: dict[str, Any] | None = None,
    bounds: dict[str, float] | None = None,
) -> dict[str, Any]:
    lat = float(location["lat"])
    lon = float(location["lon"])
    area_bounds = bounds or _bounds_from_location(location)
    return {
        "nasa_power": (
            fetch_nasa_power_context(lat, lon)
            if _env_enabled("NASA_POWER_ENABLED", default=True)
            else _not_configured("nasa-power", "NASA POWER was disabled with NASA_POWER_ENABLED=0.")
        ),
        "worldpop": fetch_worldpop_exposure(location),
        "firms": fetch_firms_fire_context(lat, lon, json.dumps(area_bounds, sort_keys=True)),
        "shakemap": (
            fetch_shakemap_summary(closest_earthquake.get("id"))
            if closest_earthquake and _env_enabled("SHAKEMAP_ENABLED", default=True)
            else _not_configured("usgs-shakemap", "No recent earthquake ShakeMap lookup was needed for this selected record.")
        ),
        "copernicus_clms": _configured_provider_status("copernicus-clms", "COPERNICUS_CLMS_ENABLED"),
        "nohrsc": _configured_provider_status("noaa-nohrsc", "NOHRSC_ENABLED"),
    }


@lru_cache(maxsize=512)
def fetch_nasa_power_context(lat: float, lon: float) -> dict[str, Any]:
    end_date = date.today() - timedelta(days=3)
    start_date = end_date - timedelta(days=44)
    params = {
        "parameters": "T2M,T2M_MAX,T2M_MIN,PRECTOTCORR,RH2M,WS10M,GWETTOP,GWETROOT",
        "community": "AG",
        "longitude": round(lon, 4),
        "latitude": round(lat, 4),
        "start": start_date.strftime("%Y%m%d"),
        "end": end_date.strftime("%Y%m%d"),
        "format": "JSON",
        "time-standard": "UTC",
    }
    try:
        response = requests.get(NASA_POWER_DAILY_URL, params=params, timeout=8)
        response.raise_for_status()
        parameter_data = ((response.json().get("properties") or {}).get("parameter")) or {}
        precipitation = _power_series(parameter_data.get("PRECTOTCORR"))
        temperatures = _power_series(parameter_data.get("T2M"))
        soil_top = _power_series(parameter_data.get("GWETTOP"))
        soil_root = _power_series(parameter_data.get("GWETROOT"))
        humidity = _power_series(parameter_data.get("RH2M"))
        wind = _power_series(parameter_data.get("WS10M"))
        return {
            "source": "nasa-power",
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "precipitation_30d_mm": round(sum(precipitation[-30:]), 2) if precipitation else None,
            "temperature_30d_mean_c": round(mean(temperatures[-30:]), 2) if temperatures else None,
            "soil_wetness_top_mean": round(mean(soil_top[-7:]), 3) if soil_top else None,
            "soil_wetness_root_mean": round(mean(soil_root[-7:]), 3) if soil_root else None,
            "humidity_7d_mean_pct": round(mean(humidity[-7:]), 2) if humidity else None,
            "wind_7d_mean_m_s": round(mean(wind[-7:]), 2) if wind else None,
        }
    except Exception as error:
        return _unavailable("nasa-power", str(error))


@lru_cache(maxsize=256)
def fetch_worldpop_exposure_cached(location_id: str, bounds_json: str, baseline_exposure: float, api_key: str | None) -> dict[str, Any]:
    if not _env_enabled("WORLDPOP_ENABLED", default=True):
        return {
            **_not_configured("worldpop", "WorldPop was disabled with WORLDPOP_ENABLED=0; static exposure metadata is used."),
            "exposure_index": baseline_exposure,
        }

    bounds = json.loads(bounds_json)
    polygon = _bounds_polygon(bounds)
    geojson = {
        "type": "FeatureCollection",
        "features": [{"type": "Feature", "properties": {}, "geometry": {"type": "Polygon", "coordinates": [polygon]}}],
    }
    params: dict[str, Any] = {
        "dataset": "wpgppop",
        "year": "2020",
        "geojson": json.dumps(geojson, separators=(",", ":")),
        "runasync": "false",
    }
    if api_key:
        params["key"] = api_key
    try:
        response = requests.get(WORLDPOP_STATS_URL, params=params, timeout=8)
        response.raise_for_status()
        payload = response.json()
        total_population = ((payload.get("data") or {}).get("total_population")) if not payload.get("error") else None
        if total_population is None:
            return _unavailable("worldpop", payload.get("error_message") or "WorldPop task did not return a population total.")
        area_km2 = _bounds_area_km2(bounds)
        density = float(total_population) / max(1.0, area_km2)
        exposure_index = min(100, max(0, 15 + math.log10(max(1, density)) * 28))
        return {
            "source": "worldpop",
            "population_total": round(float(total_population), 0),
            "area_km2": round(area_km2, 1),
            "population_density_km2": round(density, 2),
            "exposure_index": round(exposure_index, 2),
        }
    except Exception as error:
        return {
            **_unavailable("worldpop", str(error)),
            "exposure_index": baseline_exposure,
        }


def fetch_worldpop_exposure(location: dict[str, Any]) -> dict[str, Any]:
    bounds = _bounds_from_location(location)
    return fetch_worldpop_exposure_cached(
        location.get("id", "unknown"),
        json.dumps(bounds, sort_keys=True),
        float(location.get("exposure_index", 50)),
        os.getenv("WORLDPOP_API_KEY"),
    )


@lru_cache(maxsize=512)
def fetch_firms_fire_context(lat: float, lon: float, bounds_json: str | None = None) -> dict[str, Any]:
    map_key = os.getenv("NASA_FIRMS_MAP_KEY") or os.getenv("FIRMS_MAP_KEY")
    if not map_key:
        return _not_configured("nasa-firms", "NASA FIRMS requires a free map key. Set NASA_FIRMS_MAP_KEY to use live active-fire detections.")

    bounds = json.loads(bounds_json) if bounds_json else None
    bounds = bounds or _small_bounds(lat, lon, 1.0)
    area = f"{bounds['west']},{bounds['south']},{bounds['east']},{bounds['north']}"
    url = f"{FIRMS_AREA_URL}/{map_key}/VIIRS_SNPP_NRT/{area}/2"
    try:
        response = requests.get(url, timeout=8)
        response.raise_for_status()
        rows = list(csv.DictReader(response.text.splitlines()))
        nearest_km = None
        for row in rows:
            fire_lat = float(row.get("latitude") or 0)
            fire_lon = float(row.get("longitude") or 0)
            distance = haversine(lat, lon, fire_lat, fire_lon)
            nearest_km = distance if nearest_km is None else min(nearest_km, distance)
        proximity = 0 if nearest_km is None else max(0, 100 - nearest_km * 2.5)
        count_factor = min(40, len(rows) * 4)
        return {
            "source": "nasa-firms",
            "active_fire_count": len(rows),
            "nearest_fire_km": round(nearest_km, 1) if nearest_km is not None else None,
            "active_fire_proximity": round(min(100, proximity + count_factor), 2),
        }
    except Exception as error:
        return _unavailable("nasa-firms", str(error))


@lru_cache(maxsize=256)
def fetch_shakemap_summary(event_id: str | None) -> dict[str, Any]:
    if not event_id:
        return _unavailable("usgs-shakemap", "No USGS event id was provided.")
    try:
        response = requests.get(USGS_EVENT_URL, params={"eventid": event_id, "format": "geojson"}, timeout=6)
        response.raise_for_status()
        products = ((response.json().get("properties") or {}).get("products") or {}).get("shakemap") or []
        if not products:
            return _unavailable("usgs-shakemap", "This recent event has no ShakeMap product.")
        product = products[-1]
        contents = product.get("contents") or {}
        grid = contents.get("download/grid.xml") or contents.get("grid.xml")
        grid_url = grid.get("url") if isinstance(grid, dict) else None
        if not grid_url:
            return {"source": "usgs-shakemap", "status": "available", "event_id": event_id, "mmi_max": None, "note": "ShakeMap product exists, but grid.xml was not listed."}
        grid_response = requests.get(grid_url, timeout=8)
        grid_response.raise_for_status()
        mmi_values = _parse_shakemap_mmi(grid_response.text)
        if not mmi_values:
            return {"source": "usgs-shakemap", "status": "available", "event_id": event_id, "mmi_max": None, "note": "ShakeMap grid parsed, but no MMI field was found."}
        return {
            "source": "usgs-shakemap",
            "event_id": event_id,
            "mmi_max": round(max(mmi_values), 2),
            "mmi_mean": round(mean(mmi_values), 2),
            "sample_count": len(mmi_values),
        }
    except Exception as error:
        return _unavailable("usgs-shakemap", str(error))


def _parse_shakemap_mmi(xml_text: str) -> list[float]:
    root = ElementTree.fromstring(xml_text)
    fields: dict[int, str] = {}
    for field in root.iter():
        if field.tag.endswith("grid_field"):
            fields[int(field.attrib.get("index", "0"))] = field.attrib.get("name", "").upper()
    mmi_index = next((index for index, name in fields.items() if name == "MMI"), None)
    if not mmi_index:
        return []
    data_text = ""
    for element in root.iter():
        if element.tag.endswith("grid_data"):
            data_text = element.text or ""
            break
    values = []
    for line in data_text.splitlines():
        parts = line.split()
        if len(parts) >= mmi_index:
            try:
                values.append(float(parts[mmi_index - 1]))
            except ValueError:
                continue
    return values


def _power_series(values: dict[str, Any] | None) -> list[float]:
    if not values:
        return []
    series = []
    for value in values.values():
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if number <= -900:
            continue
        series.append(number)
    return series


def _bounds_from_location(location: dict[str, Any]) -> dict[str, float]:
    bounds = location.get("bounds")
    if bounds and len(bounds) == 2:
        return {
            "south": float(bounds[0][0]),
            "west": float(bounds[0][1]),
            "north": float(bounds[1][0]),
            "east": float(bounds[1][1]),
        }
    return _small_bounds(float(location["lat"]), float(location["lon"]), 1.0)


def _small_bounds(lat: float, lon: float, radius_degrees: float) -> dict[str, float]:
    return {"south": lat - radius_degrees, "west": lon - radius_degrees, "north": lat + radius_degrees, "east": lon + radius_degrees}


def _bounds_polygon(bounds: dict[str, float]) -> list[list[float]]:
    return [
        [bounds["west"], bounds["south"]],
        [bounds["east"], bounds["south"]],
        [bounds["east"], bounds["north"]],
        [bounds["west"], bounds["north"]],
        [bounds["west"], bounds["south"]],
    ]


def _bounds_area_km2(bounds: dict[str, float]) -> float:
    center_lat = (bounds["south"] + bounds["north"]) / 2
    width = haversine(center_lat, bounds["west"], center_lat, bounds["east"])
    height = haversine(bounds["south"], bounds["west"], bounds["north"], bounds["west"])
    return width * height


def _configured_provider_status(source: str, env_name: str) -> dict[str, Any]:
    enabled = _env_enabled(env_name)
    return {
        "source": source,
        "status": "configured" if enabled else "not_configured",
        "note": f"{source} adapter is reserved for heavier raster workflows; set {env_name}=1 after configuring credentials/data access.",
    }


def _unavailable(source: str, reason: str) -> dict[str, Any]:
    return {"source": source, "status": "unavailable", "reason": reason}


def _not_configured(source: str, reason: str) -> dict[str, Any]:
    return {"source": source, "status": "not_configured", "reason": reason}


def _env_enabled(name: str, default: bool = False) -> bool:
    fallback = "1" if default else "0"
    return os.getenv(name, fallback).strip().lower() in {"1", "true", "yes"}
