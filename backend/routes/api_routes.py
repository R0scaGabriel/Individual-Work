from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from services.external_data_service import fetch_external_context, fetch_nasa_power_context
from services.mock_data_service import SUPPORTED_DISASTERS, find_nearest_location, get_locations
from services.map_data_service import build_earthquake_map, build_risk_grid, build_risk_heatmap, fetch_rivers_geojson, fetch_terrain_summary
from services.normalization import (
    extract_raw_earthquake_values,
    extract_raw_indicator_values,
    nearest_earthquake,
    normalize_earthquake_indicators,
    normalize_weather_indicators,
)
from services.open_meteo_service import fetch_flood, fetch_weather
from services.risk_service import build_indicator_details, calculate_risk
from services.usgs_service import fetch_recent_earthquakes


router = APIRouter(prefix="/api")


class RiskCalculationRequest(BaseModel):
    disaster_type: str = Field(..., examples=["flood"])
    indicators: dict[str, float]


@router.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "message": "Prototype backend is running. Risk outputs are estimates, not official warnings.",
    }


@router.get("/locations")
def locations() -> list[dict[str, Any]]:
    return get_locations()


@router.get("/disasters")
def disasters() -> list[dict[str, str]]:
    return SUPPORTED_DISASTERS


@router.get("/earthquakes")
def earthquakes(strict_real: bool = Query(True)) -> list[dict[str, Any]]:
    return fetch_recent_earthquakes(allow_mock=not strict_real)


@router.get("/weather")
def weather(
    lat: float = Query(...),
    lon: float = Query(...),
    strict_real: bool = Query(True),
) -> dict[str, Any]:
    return fetch_weather(lat, lon, allow_mock=not strict_real)


@router.get("/map/rivers")
def map_rivers(
    lat: float = Query(...),
    lon: float = Query(...),
    radius_km: float = Query(15, ge=1, le=50),
    south: float | None = Query(None),
    west: float | None = Query(None),
    north: float | None = Query(None),
    east: float | None = Query(None),
    strict_real: bool = Query(True),
) -> dict[str, Any]:
    bounds = _bounds_from_query(south, west, north, east)
    return fetch_rivers_geojson(lat, lon, radius_km, bounds=bounds, allow_mock=not strict_real)


@router.get("/map/terrain")
def map_terrain(
    lat: float = Query(...),
    lon: float = Query(...),
    radius_km: float = Query(2, ge=0.2, le=20),
    strict_real: bool = Query(True),
) -> dict[str, Any]:
    return fetch_terrain_summary(lat, lon, radius_km, allow_mock=not strict_real)


@router.get("/map/heatmap")
def map_heatmap(
    disaster_type: str = Query(...),
    lat: float = Query(...),
    lon: float = Query(...),
    radius_km: float = Query(35, ge=5, le=100),
) -> dict[str, Any]:
    return build_risk_heatmap(disaster_type, lat, lon, radius_km)


@router.get("/map/earthquakes")
def map_earthquakes(
    lat: float = Query(...),
    lon: float = Query(...),
    radius_km: float = Query(1500, ge=100, le=5000),
    strict_real: bool = Query(True),
) -> dict[str, Any]:
    return build_earthquake_map(lat, lon, radius_km, allow_mock=not strict_real)


@router.get("/providers")
def providers(
    lat: float = Query(...),
    lon: float = Query(...),
    strict_real: bool = Query(True),
) -> dict[str, Any]:
    location = find_nearest_location(lat, lon)
    earthquakes_data = fetch_recent_earthquakes(allow_mock=not strict_real)
    closest_quake = nearest_earthquake(earthquakes_data, location)
    return {
        "location": location,
        "providers": fetch_external_context(location, closest_quake),
        "note": "Optional providers improve prototype indicators when available; unavailable providers do not stop the app.",
    }


@router.get("/risk/grid")
def risk_grid(
    disaster: str = Query(...),
    lat: float = Query(...),
    lon: float = Query(...),
    radius_km: float = Query(35, ge=2, le=120),
    resolution: int = Query(7, ge=3, le=15),
    south: float | None = Query(None),
    west: float | None = Query(None),
    north: float | None = Query(None),
    east: float | None = Query(None),
    strict_real: bool = Query(True),
) -> list[dict[str, Any]]:
    disaster_id = disaster.lower().strip().replace("-", "_")
    if disaster_id == "heat_wave":
        disaster_id = "heatwave"
    supported = {item["id"] for item in SUPPORTED_DISASTERS}
    if disaster_id not in supported:
        raise HTTPException(status_code=400, detail=f"Unsupported disaster type: {disaster}")
    bounds = _bounds_from_query(south, west, north, east)
    return build_risk_grid(disaster_id, lat, lon, radius_km, resolution, bounds=bounds, strict_real=strict_real)


@router.get("/risk/overview")
def risk_overview(
    strict_real: bool = Query(True),
    fast: bool = Query(True),
    optional_providers: bool = Query(False),
) -> list[dict[str, Any]]:
    locations_data = get_locations()
    allow_mock = not strict_real
    earthquakes_data = fetch_recent_earthquakes(allow_mock=allow_mock)

    def build(location: dict[str, Any]) -> dict[str, Any]:
        return _risk_bundle_for_location(
            location,
            strict_real=strict_real,
            earthquakes_data=earthquakes_data,
            fast_terrain=fast,
            include_optional_providers=optional_providers,
        )

    with ThreadPoolExecutor(max_workers=min(3, max(1, len(locations_data)))) as executor:
        return list(executor.map(build, locations_data))


@router.get("/risk/all")
def risk_all(
    lat: float = Query(...),
    lon: float = Query(...),
    strict_real: bool = Query(True),
) -> dict[str, Any]:
    location = find_nearest_location(lat, lon)
    return _risk_bundle_for_location(location, strict_real=strict_real)


def _risk_bundle_for_location(
    location: dict[str, Any],
    strict_real: bool,
    earthquakes_data: list[dict[str, Any]] | None = None,
    fast_terrain: bool = False,
    include_optional_providers: bool = True,
) -> dict[str, Any]:
    allow_mock = not strict_real
    weather_data = fetch_weather(location["lat"], location["lon"], allow_mock=allow_mock)
    flood_data = fetch_flood(location["lat"], location["lon"], allow_mock=allow_mock)
    earthquakes_data = earthquakes_data if earthquakes_data is not None else fetch_recent_earthquakes(allow_mock=allow_mock)
    closest_quake = nearest_earthquake(earthquakes_data, location)
    external_context = (
        fetch_external_context(location, closest_quake)
        if include_optional_providers
        else _optimized_overview_provider_context()
    )
    if strict_real and weather_data.get("source") == "unavailable":
        nasa_power_context = fetch_nasa_power_context(float(location["lat"]), float(location["lon"]))
        if nasa_power_context.get("source") == "nasa-power" and nasa_power_context.get("status") != "unavailable":
            weather_data = _weather_from_nasa_power(location, nasa_power_context)
            external_context = {**external_context, "nasa_power": nasa_power_context}
    terrain_data = _country_metadata_terrain(location) if fast_terrain else (
        fetch_terrain_summary(location["lat"], location["lon"], radius_km=2, allow_mock=False)
        if strict_real
        else _country_metadata_terrain(location, source="sample-location")
    )
    if strict_real and terrain_data.get("source") == "unavailable":
        terrain_data = _country_metadata_terrain(location)
    indicators_by_type = normalize_weather_indicators(weather_data, flood_data, location, terrain_data, external_context)
    indicators_by_type["earthquake"] = normalize_earthquake_indicators(closest_quake, location, external_context)
    raw_values_by_type = extract_raw_indicator_values(weather_data, flood_data, location, terrain_data, external_context)
    raw_values_by_type["earthquake"] = extract_raw_earthquake_values(closest_quake, location, external_context)
    if strict_real and terrain_data.get("source") == "unavailable":
        raw_values_by_type["flood"]["low_elevation"]["value"] = None
        raw_values_by_type["flood"]["low_elevation"]["unit"] = "unavailable"
        indicators_by_type["flood"]["low_elevation"] = 0

    results = []
    for disaster in SUPPORTED_DISASTERS:
        disaster_id = disaster["id"]
        if strict_real and weather_data.get("source") == "unavailable" and disaster_id != "earthquake":
            risk = _unavailable_risk(disaster_id, "Real Open-Meteo weather data is unavailable, so no demo risk is displayed.")
        else:
            risk = calculate_risk(disaster_id, indicators_by_type[disaster_id])
        risk["indicator_details"] = build_indicator_details(
            disaster_id,
            risk["indicators"],
            raw_values_by_type.get(disaster_id),
        )
        results.append(
            {
                **risk,
                "label": disaster["label"],
                "location": location,
                "lat": location["lat"],
                "lon": location["lon"],
                "related_event": closest_quake if disaster_id == "earthquake" else None,
            }
        )

    return {
        "location": location,
        "weather": weather_data,
        "flood": flood_data,
        "terrain": terrain_data,
        "providers": external_context,
        "nearest_earthquake": closest_quake,
        "results": results,
        "scientific_note": (
            "Scores are prototype risk estimations using public data, normalized indicators, and mathematical formulas. "
            "They require regional calibration and historical validation before real operational use."
        ),
    }


@router.post("/risk/calculate")
def risk_calculate(payload: RiskCalculationRequest) -> dict[str, Any]:
    try:
        result = calculate_risk(payload.disaster_type, payload.indicators)
        result["indicator_details"] = build_indicator_details(payload.disaster_type, result["indicators"])
        return result
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


def _country_metadata_terrain(location: dict[str, Any], source: str = "country-metadata") -> dict[str, Any]:
    return {
        "source": source,
        "elevation_m": float(location.get("reference_elevation_m", 150)),
        "slope_degrees": round(float(location.get("slope_index", 40)) * 0.55, 1),
        "note": "Static country terrain metadata is used for fast overview scoring; detailed terrain endpoints can sample OpenTopoData.",
    }


def _optimized_overview_provider_context() -> dict[str, dict[str, str]]:
    return {
        "open_meteo": {
            "source": "open-meteo",
            "status": "configured",
            "reason": "Weather and flood indicators are still requested from Open-Meteo; responses are cached briefly.",
        },
        "usgs": {
            "source": "usgs",
            "status": "configured",
            "reason": "The recent earthquake feed is fetched once and reused for all countries in the overview request.",
        },
        "terrain": {
            "source": "country-metadata",
            "status": "configured",
            "reason": "Fast overview mode uses static terrain metadata instead of one OpenTopoData request per country.",
        },
        "optional_providers": {
            "source": "optimized-overview",
            "status": "unavailable",
            "reason": "NASA POWER, FIRMS, WorldPop, ShakeMap, CLMS, and NOHRSC are skipped in dashboard overview mode for speed.",
        },
    }


def _weather_from_nasa_power(location: dict[str, Any], nasa_power: dict[str, Any]) -> dict[str, Any]:
    temperature = float(nasa_power.get("temperature_30d_mean_c") or location.get("baseline_temperature", 18))
    precipitation_30d = float(nasa_power.get("precipitation_30d_mm") or 0)
    daily_precipitation = precipitation_30d / 30
    humidity = float(nasa_power.get("humidity_7d_mean_pct") or 55)
    wind_kmh = float(nasa_power.get("wind_7d_mean_m_s") or 0) * 3.6
    today = date.today()
    daily = []
    for offset in range(29, -1, -1):
        day = today - timedelta(days=offset)
        daily.append(
            {
                "date": day.isoformat(),
                "temperature": round(temperature, 1),
                "temperature_max": round(temperature + 3, 1),
                "temperature_min": round(temperature - 3, 1),
                "apparent_temperature_max": round(temperature + 3, 1),
                "apparent_temperature_min": round(temperature - 3, 1),
                "precipitation": round(daily_precipitation, 2),
                "rain": round(daily_precipitation, 2),
                "snowfall": 0,
                "humidity": humidity,
                "wind_speed": round(wind_kmh, 1),
                "wind_gusts": round(wind_kmh * 1.4, 1),
                "et0": 0,
            }
        )
    return {
        "source": "nasa-power-derived",
        "latitude": location["lat"],
        "longitude": location["lon"],
        "current": {
            "temperature_2m": round(temperature, 1),
            "relative_humidity_2m": round(humidity, 1),
            "apparent_temperature": round(temperature, 1),
            "precipitation": 0,
            "rain": 0,
            "snowfall": 0,
            "wind_speed_10m": round(wind_kmh, 1),
            "wind_gusts_10m": round(wind_kmh * 1.4, 1),
            "snow_depth": 0,
            "freezing_level_height": None,
            "vapor_pressure_deficit": None,
            "et0_fao_evapotranspiration": None,
            "recent_snowfall": 0,
        },
        "daily": daily,
        "note": "Open-Meteo weather was unavailable, so NASA POWER aggregate climate data was used as a public-data fallback.",
    }


def _bounds_from_query(
    south: float | None,
    west: float | None,
    north: float | None,
    east: float | None,
) -> dict[str, float] | None:
    values = [south, west, north, east]
    if all(value is None for value in values):
        return None
    if any(value is None for value in values):
        raise HTTPException(status_code=400, detail="south, west, north, and east must be provided together.")
    return {"south": float(south), "west": float(west), "north": float(north), "east": float(east)}


def _unavailable_risk(disaster_id: str, reason: str) -> dict[str, Any]:
    return {
        "risk_score": 0,
        "probability": 0,
        "risk_level": "Not Applicable",
        "hazard_index": 0,
        "disaster_type": disaster_id,
        "indicators": {},
        "calculation_engine": "real_data_unavailable",
        "explanation": reason,
        "recommendation": "Connect to the public API or choose another area/time before interpreting this prototype layer.",
    }
