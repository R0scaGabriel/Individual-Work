from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import math
from typing import Any

import requests

from .external_data_service import fetch_external_context
from .mock_data_service import find_nearest_location, mock_fire_detections
from .normalization import (
    extract_raw_earthquake_values,
    extract_raw_indicator_values,
    haversine,
    nearest_earthquake,
    normalize_earthquake_indicators,
    normalize_weather_indicators,
)
from .open_meteo_service import fetch_flood, fetch_weather
from .risk_service import build_indicator_details, calculate_risk
from .usgs_service import fetch_recent_earthquakes


OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OPENTOPO_URL = "https://api.opentopodata.org/v1/mapzen"


def fetch_rivers_geojson(
    lat: float,
    lon: float,
    radius_km: float = 15,
    bounds: dict[str, float] | None = None,
    allow_mock: bool = True,
) -> dict[str, Any]:
    radius_m = int(max(1, min(radius_km, 50)) * 1000)
    if bounds:
        south, west, north, east = bounds["south"], bounds["west"], bounds["north"], bounds["east"]
        query = f"""
        [out:json][timeout:25];
        (
          way["waterway"~"^(river|stream|canal)$"]({south},{west},{north},{east});
        );
        out geom;
        """
    else:
        query = f"""
        [out:json][timeout:25];
        (
          way(around:{radius_m},{lat},{lon})["waterway"~"^(river|stream|canal)$"];
        );
        out geom;
        """
    try:
        response = requests.post(OVERPASS_URL, data={"data": query}, timeout=15)
        response.raise_for_status()
        features = []
        for element in response.json().get("elements", []):
            geometry = element.get("geometry") or []
            coordinates = [[point["lon"], point["lat"]] for point in geometry if "lat" in point and "lon" in point]
            if len(coordinates) < 2:
                continue
            tags = element.get("tags") or {}
            features.append(
                {
                    "type": "Feature",
                    "geometry": {"type": "LineString", "coordinates": coordinates},
                    "properties": {
                        "id": element.get("id"),
                        "name": tags.get("name") or tags.get("waterway") or "Unnamed waterway",
                        "waterway": tags.get("waterway", "river"),
                        "source": "overpass",
                    },
                }
            )
        return {"type": "FeatureCollection", "features": features, "source": "overpass"}
    except Exception as error:
        if allow_mock:
            return _mock_rivers_geojson(lat, lon)
        return {"type": "FeatureCollection", "features": [], "source": "unavailable", "error": str(error)}


def fetch_terrain_summary(lat: float, lon: float, radius_km: float = 2, allow_mock: bool = True) -> dict[str, Any]:
    points = _terrain_sample_points(lat, lon, radius_km)
    elevations = _fetch_elevations(points)
    if not elevations:
        if not allow_mock:
            return {
                "source": "unavailable",
                "error": "OpenTopoData terrain request failed or returned no elevation samples.",
                "elevation_m": None,
                "slope_degrees": None,
                "samples": [],
            }
        location = find_nearest_location(lat, lon)
        return {
            "source": "mock",
            "elevation_m": _mock_elevation(location),
            "slope_degrees": round(float(location.get("slope_index", 40)) * 0.55, 1),
            "samples": [],
        }

    center = elevations[0]
    center_elev = center.get("elevation")
    slopes = []
    for sample in elevations[1:]:
        elevation = sample.get("elevation")
        if center_elev is None or elevation is None:
            continue
        distance_m = max(
            1,
            haversine(
                center["location"]["lat"],
                center["location"]["lng"],
                sample["location"]["lat"],
                sample["location"]["lng"],
            )
            * 1000,
        )
        slopes.append(math.degrees(math.atan(abs(float(elevation) - float(center_elev)) / distance_m)))

    return {
        "source": "opentopodata",
        "elevation_m": center_elev,
        "slope_degrees": round(max(slopes) if slopes else 0, 1),
        "samples": elevations,
    }


def build_risk_heatmap(disaster_type: str, lat: float, lon: float, radius_km: float = 35) -> dict[str, Any]:
    disaster_type = disaster_type.lower()
    if disaster_type not in {"drought", "heatwave", "landslide", "avalanche"}:
        return {"disaster_type": disaster_type, "points": [], "source": "not_applicable"}

    base_location = find_nearest_location(lat, lon)
    grid = _grid_points(lat, lon, radius_km, size=3)
    weather = fetch_weather(lat, lon)
    flood = fetch_flood(lat, lon)
    terrain = fetch_terrain_summary(lat, lon, radius_km=2)
    points = []

    for index, point in enumerate(grid):
        local_location = dict(base_location)
        local_location["lat"] = point["lat"]
        local_location["lon"] = point["lon"]
        local_terrain = dict(terrain)
        local_terrain["slope_degrees"] = max(0, float(terrain.get("slope_degrees") or 0) + point["offset_weight"] * 4)
        local_weather = _adjust_weather_for_grid(weather, point["offset_weight"], disaster_type)
        indicators = normalize_weather_indicators(local_weather, flood, local_location, local_terrain)[disaster_type]
        risk = calculate_risk(disaster_type, indicators)
        points.append(
            {
                "id": f"{disaster_type}-grid-{index}",
                "lat": point["lat"],
                "lon": point["lon"],
                "intensity": round(risk["risk_score"] / 100, 3),
                "risk_score": risk["risk_score"],
                "risk_level": risk["risk_level"],
                "indicators": indicators,
            }
        )

    return {
        "disaster_type": disaster_type,
        "points": points,
        "source": "weather-grid-with-terrain" if disaster_type in {"landslide", "avalanche"} else "weather-grid",
        "terrain": terrain,
    }


def build_earthquake_map(lat: float, lon: float, radius_km: float = 1500, allow_mock: bool = True) -> dict[str, Any]:
    earthquakes = fetch_recent_earthquakes(limit=80, allow_mock=allow_mock)
    events = []
    heatmap_points = []
    for quake in earthquakes:
        distance_km = haversine(lat, lon, float(quake.get("lat") or 0), float(quake.get("lon") or 0))
        if distance_km > radius_km:
            continue
        magnitude = float(quake.get("magnitude") or 0)
        depth = float(quake.get("depth") or 0)
        shallow_factor = max(0, min(1, 1 - depth / 250))
        distance_factor = math.exp(-(distance_km / 100))
        intensity = max(0, min(1, (magnitude / 8) * 0.55 + shallow_factor * 0.20 + distance_factor * 0.25))
        event = {
            **quake,
            "distance_km": round(distance_km, 1),
            "display_radius": round(max(5, magnitude * 4), 1),
            "intensity": round(intensity, 3),
        }
        events.append(event)
        heatmap_points.append(
            {
                "lat": quake.get("lat"),
                "lon": quake.get("lon"),
                "intensity": round(intensity, 3),
                "magnitude": magnitude,
                "depth": depth,
                "distance_km": round(distance_km, 1),
            }
        )
    return {"events": events, "heatmap_points": heatmap_points, "source": "usgs" if earthquakes else "unavailable"}


def build_risk_grid(
    disaster_type: str,
    lat: float,
    lon: float,
    radius_km: float = 35,
    resolution: int = 7,
    bounds: dict[str, float] | None = None,
    strict_real: bool = False,
) -> list[dict[str, Any]]:
    disaster_type = _canonical_disaster(disaster_type)
    resolution = max(3, min(15, int(resolution)))
    radius_km = max(2, min(120, float(radius_km)))
    base_location = find_nearest_location(lat, lon)
    cells = _grid_cells_for_bounds(bounds, resolution) if bounds else _grid_cells(lat, lon, radius_km, resolution)
    allow_mock = not strict_real
    weather = fetch_weather(lat, lon, allow_mock=allow_mock)
    flood = fetch_flood(lat, lon, allow_mock=allow_mock)
    rivers = (
        fetch_rivers_geojson(lat, lon, min(50, max(10, radius_km)), bounds=bounds, allow_mock=allow_mock)
        if disaster_type == "flood"
        else None
    )
    terrain = (
        fetch_terrain_summary(lat, lon, radius_km=2, allow_mock=allow_mock)
        if disaster_type in {"landslide", "avalanche", "flood"}
        else {}
    )
    terrain_by_cell = (
        _terrain_by_cell_from_elevation_api(cells, base_location) if strict_real and disaster_type in {"landslide", "avalanche", "flood"} else {}
    )
    weather_by_cell = _weather_by_cell_from_api(cells) if strict_real and disaster_type != "earthquake" else {}
    flood_by_cell = _flood_by_cell_from_api(cells) if strict_real and disaster_type == "flood" else {}
    earthquakes = fetch_recent_earthquakes(limit=80, allow_mock=allow_mock) if disaster_type == "earthquake" else []
    active_fires = [] if strict_real else (mock_fire_detections(lat, lon) if disaster_type == "wildfire" else [])
    external_context = fetch_external_context(
        base_location,
        nearest_earthquake(earthquakes, base_location) if earthquakes else None,
        bounds=bounds,
    )

    grid = []
    for index, cell in enumerate(cells):
        local_location = dict(base_location)
        local_location["lat"] = cell["lat"]
        local_location["lon"] = cell["lon"]
        local_terrain = terrain_by_cell.get(index) or _terrain_for_cell(terrain, base_location, cell)
        local_weather = weather_by_cell.get(index) or (
            weather if strict_real else _adjust_weather_for_grid(weather, cell["offset_weight"], disaster_type)
        )
        local_flood = flood_by_cell.get(index) or flood

        if disaster_type == "earthquake":
            closest_quake = nearest_earthquake(earthquakes, local_location)
            normalized = normalize_earthquake_indicators(closest_quake, local_location, external_context)
            raw_details = extract_raw_earthquake_values(closest_quake, local_location, external_context)
            context = {"closest_earthquake": closest_quake, "providers": external_context}
        else:
            raw_by_type = extract_raw_indicator_values(local_weather, local_flood, local_location, local_terrain, external_context)
            normalized_by_type = normalize_weather_indicators(local_weather, local_flood, local_location, local_terrain, external_context)
            raw_details = raw_by_type[disaster_type]
            normalized = normalized_by_type[disaster_type]
            if strict_real and disaster_type == "wildfire" and (external_context.get("firms") or {}).get("source") != "nasa-firms":
                raw_details["active_fire_proximity"]["value"] = 0
                raw_details["active_fire_proximity"]["unit"] = "not configured"
                normalized["active_fire_proximity"] = 0
            if strict_real and disaster_type == "flood" and local_terrain.get("source") == "unavailable":
                raw_details["low_elevation"]["value"] = None
                raw_details["low_elevation"]["unit"] = "unavailable"
                normalized["low_elevation"] = 0
            context = {
                "rivers": rivers,
                "active_fires": active_fires,
                "terrain": local_terrain,
                "flood_source": local_flood.get("source", "unknown"),
                "weather_source": local_weather.get("source", "unknown"),
                "strict_real": strict_real,
                "providers": external_context,
            }

        applicability = _applicability_for_cell(disaster_type, cell, raw_details, normalized, context)
        if applicability["applicable"]:
            risk = calculate_risk(disaster_type, normalized)
            reason = _positive_reason(disaster_type, raw_details, risk, context)
        else:
            risk = _not_applicable_result(disaster_type, normalized)
            reason = applicability["reason"]

        indicator_details = build_indicator_details(disaster_type, normalized, raw_details)
        grid.append(
            {
                "id": f"{disaster_type}-cell-{index}",
                "lat": cell["lat"],
                "lon": cell["lon"],
                "bounds": cell["bounds"],
                "cell_size_km": cell["cell_size_km"],
                "disaster_type": disaster_type,
                "risk_score": risk["risk_score"],
                "risk_level": risk["risk_level"],
                "probability": risk["probability"],
                "model_family": risk.get("model_family", "Applicability mask"),
                "applicable": applicability["applicable"],
                "reason": reason,
                "indicators": _flatten_raw_indicators(raw_details),
                "normalized_indicators": normalized,
                "indicator_details": indicator_details,
                "applicability": applicability,
                "source": context.get("weather_source", "usgs-or-derived"),
                "providers": external_context,
            }
        )
    return grid


def _fetch_elevations(points: list[dict[str, float]]) -> list[dict[str, Any]]:
    locations = "|".join(f"{point['lat']:.5f},{point['lon']:.5f}" for point in points[:25])
    try:
        response = requests.get(
            OPENTOPO_URL,
            params={"locations": locations, "interpolation": "bilinear"},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        if data.get("status") != "OK":
            return []
        return data.get("results") or []
    except Exception:
        return []


def _terrain_sample_points(lat: float, lon: float, radius_km: float) -> list[dict[str, float]]:
    offset = max(0.005, radius_km / 111)
    lon_offset = offset / max(0.2, math.cos(math.radians(lat)))
    return [
        {"lat": lat, "lon": lon},
        {"lat": lat + offset, "lon": lon},
        {"lat": lat - offset, "lon": lon},
        {"lat": lat, "lon": lon + lon_offset},
        {"lat": lat, "lon": lon - lon_offset},
    ]


def _grid_points(lat: float, lon: float, radius_km: float, size: int = 3) -> list[dict[str, float]]:
    half = size // 2
    lat_step = (radius_km / 111) / max(1, half)
    lon_step = lat_step / max(0.2, math.cos(math.radians(lat)))
    points = []
    for y in range(-half, half + 1):
        for x in range(-half, half + 1):
            points.append(
                {
                    "lat": round(lat + y * lat_step, 5),
                    "lon": round(lon + x * lon_step, 5),
                    "offset_weight": round((abs(x) + abs(y)) / max(1, half * 2), 2),
                }
            )
    return points


def _grid_cells(lat: float, lon: float, radius_km: float, resolution: int) -> list[dict[str, Any]]:
    half_span_lat = radius_km / 111
    half_span_lon = half_span_lat / max(0.2, math.cos(math.radians(lat)))
    lat_step = (half_span_lat * 2) / resolution
    lon_step = (half_span_lon * 2) / resolution
    cell_size_km = (radius_km * 2) / resolution
    cells = []
    for row in range(resolution):
        south = lat - half_span_lat + row * lat_step
        north = south + lat_step
        center_lat = (south + north) / 2
        for col in range(resolution):
            west = lon - half_span_lon + col * lon_step
            east = west + lon_step
            center_lon = (west + east) / 2
            distance = haversine(lat, lon, center_lat, center_lon)
            if distance > radius_km * 1.25:
                continue
            cells.append(
                {
                    "lat": round(center_lat, 5),
                    "lon": round(center_lon, 5),
                    "bounds": [[round(south, 5), round(west, 5)], [round(north, 5), round(east, 5)]],
                    "row": row,
                    "col": col,
                    "offset_weight": round(min(1, distance / max(1, radius_km)), 3),
                    "cell_size_km": round(cell_size_km, 2),
                }
            )
    return cells


def _grid_cells_for_bounds(bounds: dict[str, float], resolution: int) -> list[dict[str, Any]]:
    south = max(-89.5, min(89.5, float(bounds["south"])))
    north = max(-89.5, min(89.5, float(bounds["north"])))
    west = max(-180, min(180, float(bounds["west"])))
    east = max(-180, min(180, float(bounds["east"])))
    if south > north:
        south, north = north, south
    if west > east:
        west, east = east, west

    lat_step = (north - south) / resolution
    lon_step = (east - west) / resolution
    center_lat = (south + north) / 2
    center_lon = (west + east) / 2
    approximate_width = haversine(center_lat, west, center_lat, east)
    approximate_height = haversine(south, center_lon, north, center_lon)
    cell_size_km = max(approximate_width, approximate_height) / resolution
    max_distance = max(1, haversine(south, west, center_lat, center_lon))

    cells = []
    for row in range(resolution):
        cell_south = south + row * lat_step
        cell_north = cell_south + lat_step
        cell_lat = (cell_south + cell_north) / 2
        for col in range(resolution):
            cell_west = west + col * lon_step
            cell_east = cell_west + lon_step
            cell_lon = (cell_west + cell_east) / 2
            distance = haversine(center_lat, center_lon, cell_lat, cell_lon)
            cells.append(
                {
                    "lat": round(cell_lat, 5),
                    "lon": round(cell_lon, 5),
                    "bounds": [[round(cell_south, 5), round(cell_west, 5)], [round(cell_north, 5), round(cell_east, 5)]],
                    "row": row,
                    "col": col,
                    "offset_weight": round(min(1, distance / max_distance), 3),
                    "cell_size_km": round(max(1, cell_size_km), 2),
                }
            )
    return cells


def _weather_by_cell_from_api(cells: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    def fetch(index_and_cell: tuple[int, dict[str, Any]]) -> tuple[int, dict[str, Any]]:
        index, cell = index_and_cell
        return index, fetch_weather(cell["lat"], cell["lon"], allow_mock=False)

    with ThreadPoolExecutor(max_workers=8) as executor:
        return dict(executor.map(fetch, enumerate(cells)))


def _flood_by_cell_from_api(cells: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    def fetch(index_and_cell: tuple[int, dict[str, Any]]) -> tuple[int, dict[str, Any]]:
        index, cell = index_and_cell
        return index, fetch_flood(cell["lat"], cell["lon"], allow_mock=False)

    with ThreadPoolExecutor(max_workers=6) as executor:
        return dict(executor.map(fetch, enumerate(cells)))


def _terrain_by_cell_from_elevation_api(cells: list[dict[str, Any]], base_location: dict[str, Any]) -> dict[int, dict[str, Any]]:
    elevations = _fetch_elevations_in_chunks([{"lat": cell["lat"], "lon": cell["lon"]} for cell in cells])
    if not elevations or len(elevations) != len(cells):
        return {
            index: {
                **_terrain_for_cell({"source": "country-metadata"}, base_location, cell),
                "source": "country-metadata",
                "note": "OpenTopoData was unavailable, so static country terrain metadata was used instead of mock hazard data.",
            }
            for index, cell in enumerate(cells)
        }

    elevation_by_position = {
        (cell.get("row"), cell.get("col")): elevations[index].get("elevation")
        for index, cell in enumerate(cells)
    }
    terrain_by_index = {}
    for index, cell in enumerate(cells):
        elevation = elevations[index].get("elevation")
        neighbor_slopes = []
        for row_delta, col_delta in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            neighbor_elevation = elevation_by_position.get((cell.get("row") + row_delta, cell.get("col") + col_delta))
            if elevation is None or neighbor_elevation is None:
                continue
            distance_m = max(1, float(cell.get("cell_size_km") or 1) * 1000)
            neighbor_slopes.append(math.degrees(math.atan(abs(float(elevation) - float(neighbor_elevation)) / distance_m)))
        terrain_by_index[index] = {
            "source": "opentopodata",
            "elevation_m": elevation,
            "slope_degrees": round(max(neighbor_slopes) if neighbor_slopes else 0, 1),
            "reference_location": base_location.get("id"),
        }
    return terrain_by_index


def _fetch_elevations_in_chunks(points: list[dict[str, float]]) -> list[dict[str, Any]]:
    elevations: list[dict[str, Any]] = []
    for start in range(0, len(points), 25):
        chunk = points[start : start + 25]
        chunk_elevations = _fetch_elevations(chunk)
        if not chunk_elevations:
            return []
        elevations.extend(chunk_elevations)
    return elevations


def _adjust_weather_for_grid(weather: dict[str, Any], offset_weight: float, disaster_type: str) -> dict[str, Any]:
    adjusted = {
        **weather,
        "current": dict(weather.get("current") or {}),
        "daily": [dict(day) for day in weather.get("daily") or []],
    }
    heat_bias = offset_weight * (2.5 if disaster_type in {"drought", "heatwave", "wildfire"} else 0.8)
    rain_bias = offset_weight * (6 if disaster_type == "landslide" else (-2 if disaster_type in {"drought", "wildfire"} else 1.5))
    adjusted["current"]["temperature_2m"] = float(adjusted["current"].get("temperature_2m") or 0) + heat_bias
    adjusted["current"]["apparent_temperature"] = float(adjusted["current"].get("apparent_temperature") or 0) + heat_bias
    for day in adjusted["daily"]:
        day["temperature"] = float(day.get("temperature") or adjusted["current"]["temperature_2m"]) + heat_bias
        day["precipitation"] = max(0, float(day.get("precipitation") or 0) + rain_bias)
    return adjusted


def _terrain_for_cell(terrain: dict[str, Any], location: dict[str, Any], cell: dict[str, Any]) -> dict[str, Any]:
    base_slope = float(terrain.get("slope_degrees") or location.get("slope_index", 40) * 0.55)
    base_elevation = float(terrain.get("elevation_m") or _mock_elevation(location))
    ruggedness = float(location.get("slope_index", 40)) / 100
    return {
        **terrain,
        "slope_degrees": round(max(0, base_slope + cell["offset_weight"] * ruggedness * 8 - (1 - ruggedness) * 2), 1),
        "elevation_m": round(max(0, base_elevation + cell["offset_weight"] * ruggedness * 720), 1),
    }


def _applicability_for_cell(
    disaster_type: str,
    cell: dict[str, Any],
    raw: dict[str, dict[str, Any]],
    normalized: dict[str, float],
    context: dict[str, Any],
) -> dict[str, Any]:
    conditions: list[dict[str, Any]] = []
    strict_real = bool(context.get("strict_real"))
    weather_unavailable = context.get("weather_source") == "unavailable"
    terrain_unavailable = (context.get("terrain") or {}).get("source") == "unavailable"

    if strict_real and disaster_type != "earthquake" and weather_unavailable:
        return {
            "applicable": False,
            "reason": "Real Open-Meteo weather data is unavailable for this grid cell, so no demo risk is displayed.",
            "conditions": [_condition("Real Open-Meteo weather data available", False)],
        }

    if strict_real and disaster_type in {"landslide", "avalanche"} and terrain_unavailable:
        return {
            "applicable": False,
            "reason": "Real terrain data is unavailable for this grid cell, so terrain-dependent risk is not calculated.",
            "conditions": [_condition("Real OpenTopoData terrain data available", False)],
        }

    if disaster_type == "flood":
        rivers = context.get("rivers") or {}
        near_water = _is_near_water(cell["lat"], cell["lon"], rivers, max(2.5, cell["cell_size_km"] * 1.5))
        elevation_value = raw["low_elevation"].get("value")
        low_elevation = elevation_value is not None and float(elevation_value) <= 250
        discharge_available = float(raw["discharge_anomaly"]["value"]) > 0
        extreme_rain = float(raw["rainfall"]["value"]) >= 75
        conditions = [
            _condition("Near mapped river/stream/canal", near_water),
            _condition("Low elevation zone", low_elevation),
            _condition("River discharge data available from Open-Meteo Flood", discharge_available),
            _condition("Extreme recent rainfall", extreme_rain),
        ]
        applicable = True
        reason = (
            "Flood risk calculated because the cell is near water, low elevation, has discharge data, or has extreme rainfall."
            if near_water or low_elevation or discharge_available or extreme_rain
            else "Flood occurrence risk is low in this cell because mapped water, low elevation, discharge signal, and extreme rainfall triggers are weak."
        )
        return {"applicable": applicable, "reason": reason, "conditions": conditions}

    if disaster_type == "drought":
        deficit = float(normalized.get("precipitation_deficit", 0))
        dry_days = float(raw["dry_days"]["value"])
        recent_rain = float((raw.get("recent_precipitation_7d") or {}).get("value") or 0)
        current_rain = float((raw.get("current_precipitation") or {}).get("value") or 0)
        wet_now = current_rain >= 1 or recent_rain >= 20
        applicable = True
        reason = (
            "Current or recent rainfall is suppressing drought occurrence risk in this cell."
            if wet_now and deficit < 55
            else
            "Low 30-day precipitation and elevated temperature anomaly indicate drought stress."
            if deficit >= 45 or dry_days >= 14
            else "Drought risk calculated across the region; current accumulated indicators are weak."
        )
        conditions = [
            _condition("30-day precipitation accumulation available from Open-Meteo", True),
            _condition("Dry-day persistence considered", True),
            _condition("Current/recent rainfall relief applied", wet_now, f"{recent_rain:.1f} mm / 7 days"),
        ]
        return {"applicable": applicable, "reason": reason, "conditions": conditions}

    if disaster_type == "heatwave":
        hot_days = float(raw["consecutive_hot_days"]["value"])
        applicable = True
        conditions = [
            _condition("At least 2 recent hot days", hot_days >= 2, f"{hot_days:.0f} hot days"),
        ]
        reason = (
            "Heat-wave risk calculated because recent heat has persisted for multiple days."
            if hot_days >= 2
            else "Heat-wave occurrence risk is low because the consecutive-hot-days threshold is not currently met."
        )
        return {"applicable": applicable, "reason": reason, "conditions": conditions}

    if disaster_type == "earthquake":
        quake = context.get("closest_earthquake")
        distance = float(raw["distance_decay"]["value"])
        magnitude = float(raw["magnitude_index"]["value"])
        applicable = True
        conditions = [
            _condition("Recent USGS earthquake available", bool(quake)),
            _condition("Magnitude at least 2.5", magnitude >= 2.5, f"M {magnitude:.1f}"),
            _condition("Cell within 500 km influence radius", distance <= 500, f"{distance:.1f} km"),
        ]
        reason = (
            "Earthquake impact-risk visualization is based on recent USGS events and distance decay from the epicenter."
            if quake and magnitude >= 2.5 and distance <= 500
            else "Earthquake impact-risk is low because no recent USGS event has meaningful influence near this cell; this is not prediction."
        )
        return {"applicable": applicable, "reason": reason, "conditions": conditions}

    if disaster_type == "wildfire":
        humidity_or_rain_high = normalized.get("dryness", 0) < 25 and normalized.get("precipitation_deficit", 0) < 35
        firms_source = ((context.get("providers") or {}).get("firms") or {}).get("source")
        conditions = [
            _condition("Fire-weather indicators available from Open-Meteo", True),
            _condition("NASA FIRMS active-fire proximity configured", firms_source == "nasa-firms"),
            _condition("Moisture does not suppress risk strongly", not humidity_or_rain_high),
        ]
        reason = (
            "Fire-weather risk calculated from heat, wind, dryness, precipitation deficit, and active-fire proximity."
            if not humidity_or_rain_high
            else "Wildfire risk is reduced because humidity is high or recent precipitation is not deficient."
        )
        return {"applicable": True, "reason": reason, "conditions": conditions}

    if disaster_type == "landslide":
        slope = float(raw["slope"]["value"])
        applicable = slope >= 12
        conditions = [
            _condition("Terrain slope is relevant", applicable, f"{slope:.1f} degrees"),
            _condition("Rainfall and soil moisture indicators available", True),
        ]
        reason = (
            "Landslide risk calculated because terrain slope is relevant and rainfall/soil moisture indicators are available."
            if applicable
            else "Terrain slope is too low for landslide susceptibility."
        )
        return {"applicable": applicable, "reason": reason, "conditions": conditions}

    if disaster_type == "avalanche":
        snow_depth = float(raw["snow_depth"]["value"])
        snowfall = float(raw["recent_snowfall"]["value"])
        elevation = float((context.get("terrain") or {}).get("elevation_m") or 0)
        slope = float(raw["slope_criticality"]["value"])
        snow_ok = snow_depth >= 5 or snowfall >= 2
        elevation_ok = elevation >= 800
        slope_ok = 25 <= slope <= 60
        conditions = [
            _condition("Snow depth >= 5 cm or recent snowfall >= 2 cm", snow_ok, f"snow {snow_depth:.1f} cm, new {snowfall:.1f} cm"),
            _condition("Elevation >= 800 m", elevation_ok, f"{elevation:.0f} m"),
            _condition("Slope angle between 25 and 60 degrees", slope_ok, f"{slope:.1f} degrees"),
        ]
        if not snow_ok:
            reason = "No avalanche risk calculated because snow depth is below threshold."
        elif not elevation_ok:
            reason = "No avalanche risk calculated because terrain elevation is below mountain threshold."
        elif not slope_ok:
            reason = "No avalanche risk calculated because slope is outside avalanche-relevant range."
        else:
            reason = "Avalanche risk calculated because snow, mountain elevation, and avalanche-relevant slope conditions are present."
        return {"applicable": snow_ok and elevation_ok and slope_ok, "reason": reason, "conditions": conditions}

    return {"applicable": True, "reason": "Risk calculated for this prototype cell.", "conditions": conditions}


def _positive_reason(disaster_type: str, raw: dict[str, dict[str, Any]], risk: dict[str, Any], context: dict[str, Any]) -> str:
    if disaster_type == "flood":
        return "Flood risk reflects nearby water or low-elevation applicability plus rainfall, river discharge, and soil moisture indicators."
    if disaster_type == "drought":
        return "Drought risk uses accumulated 30-day precipitation deficit, dry days, soil moisture deficit, and temperature anomaly from Open-Meteo weather data."
    if disaster_type == "heatwave":
        return "Heat-wave risk uses persistent hot days, maximum and night temperature anomalies, and apparent temperature."
    if disaster_type == "earthquake":
        return "Earthquake impact-risk visualization uses recent USGS events, magnitude, shallow depth, and distance decay; it is not prediction."
    if disaster_type == "wildfire":
        return "Wildfire risk uses fire-weather indicators and is reduced when humidity or recent precipitation suppresses dryness."
    if disaster_type == "landslide":
        return "Landslide risk uses slope-relevant terrain with rainfall intensity, antecedent rainfall, soil moisture, and vegetation loss."
    if disaster_type == "avalanche":
        return "Avalanche risk uses snowpack, mountain elevation, critical slope angle, wind transport, and temperature change."
    return risk.get("explanation", "Risk calculated for this prototype cell.")


def _not_applicable_result(disaster_type: str, indicators: dict[str, float]) -> dict[str, Any]:
    return {
        "risk_score": 0,
        "probability": 0,
        "risk_level": "Not Applicable",
        "hazard_index": 0,
        "disaster_type": disaster_type,
        "indicators": indicators,
        "calculation_engine": "applicability_mask",
    }


def _condition(label: str, passed: bool, value: str | None = None) -> dict[str, Any]:
    return {"label": label, "passed": passed, "value": value}


def _flatten_raw_indicators(raw: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {key: item.get("value") for key, item in raw.items()}


def _is_near_water(lat: float, lon: float, rivers: dict[str, Any], threshold_km: float) -> bool:
    for feature in rivers.get("features") or []:
        coordinates = (feature.get("geometry") or {}).get("coordinates") or []
        for water_lon, water_lat in coordinates[:: max(1, len(coordinates) // 20 or 1)]:
            if haversine(lat, lon, water_lat, water_lon) <= threshold_km:
                return True
    return False


def _canonical_disaster(disaster_type: str) -> str:
    value = disaster_type.lower().strip().replace("-", "_")
    if value == "heat_wave":
        return "heatwave"
    return value


def _mock_rivers_geojson(lat: float, lon: float) -> dict[str, Any]:
    return {
        "type": "FeatureCollection",
        "source": "mock",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [lon - 0.18, lat - 0.08],
                        [lon - 0.08, lat - 0.02],
                        [lon + 0.02, lat + 0.01],
                        [lon + 0.18, lat + 0.07],
                    ],
                },
                "properties": {"name": "Mock nearby river", "waterway": "river", "source": "mock"},
            }
        ],
    }


def _mock_elevation(location: dict[str, Any]) -> float:
    if "reference_elevation_m" in location:
        return float(location["reference_elevation_m"])
    return {
        "md-moldova": 160,
        "ro-romania": 414,
        "it-italy": 538,
        "jp-japan": 438,
        "np-nepal": 3265,
        "at-austria": 910,
        "gr-greece": 498,
        "tr-turkey": 1132,
        "es-spain": 660,
        "fr-france": 375,
        "de-germany": 263,
        "pl-poland": 173,
        "ua-ukraine": 175,
        "us-california": 880,
    }.get(location.get("id"), 150)
