from __future__ import annotations

import math
from statistics import mean
from typing import Any


def clamp(value: float, minimum: float = 0, maximum: float = 100) -> float:
    return max(minimum, min(maximum, value))


def scale(value: float, low: float, high: float, inverse: bool = False) -> float:
    if high == low:
        return 0
    score = (value - low) / (high - low) * 100
    if inverse:
        score = 100 - score
    return round(clamp(score), 2)


def normalize_weather_indicators(
    weather: dict[str, Any],
    flood: dict[str, Any],
    location: dict[str, Any],
    terrain: dict[str, Any] | None = None,
    external: dict[str, Any] | None = None,
) -> dict[str, dict[str, float]]:
    raw = extract_raw_indicator_values(weather, flood, location, terrain, external)
    slope_angle = float(raw["landslide"]["slope"]["value"])

    return {
        "flood": {
            "rainfall": scale(raw["flood"]["rainfall"]["value"], 5, 100),
            "discharge_anomaly": scale(raw["flood"]["discharge_anomaly"]["value"], 75, 180),
            "soil_moisture": scale(raw["flood"]["soil_moisture"]["value"], 0, 100),
            "low_elevation": scale(raw["flood"]["low_elevation"]["value"], 1200, 0),
        },
        "wildfire": {
            "temperature": scale(raw["wildfire"]["temperature"]["value"], 18, 43),
            "wind": scale(raw["wildfire"]["wind"]["value"], 5, 45),
            "dryness": scale(raw["wildfire"]["dryness"]["value"], 0, 100),
            "precipitation_deficit": scale(raw["wildfire"]["precipitation_deficit"]["value"], 0, 100),
            "active_fire_proximity": scale(raw["wildfire"]["active_fire_proximity"]["value"], 0, 100),
        },
        "drought": {
            "precipitation_deficit": scale(raw["drought"]["precipitation_deficit"]["value"], 0, 100),
            "soil_moisture_deficit": scale(raw["drought"]["soil_moisture_deficit"]["value"], 0, 100),
            "temperature_anomaly": scale(raw["drought"]["temperature_anomaly"]["value"], 0, 18),
            "dry_days": scale(raw["drought"]["dry_days"]["value"], 0, 30),
        },
        "heatwave": {
            "max_temperature_anomaly": scale(raw["heatwave"]["max_temperature_anomaly"]["value"], 0, 18),
            "night_temperature_anomaly": scale(raw["heatwave"]["night_temperature_anomaly"]["value"], 0, 14),
            "consecutive_hot_days": scale(raw["heatwave"]["consecutive_hot_days"]["value"], 0, 7),
            "apparent_temperature": scale(raw["heatwave"]["apparent_temperature"]["value"], 24, 45),
        },
        "landslide": {
            "rainfall_intensity": scale(raw["landslide"]["rainfall_intensity"]["value"], 5, 80),
            "antecedent_rainfall": scale(raw["landslide"]["antecedent_rainfall"]["value"], 5, 120),
            "slope": scale(slope_angle, 5, 45),
            "soil_moisture": scale(raw["landslide"]["soil_moisture"]["value"], 0, 100),
            "low_vegetation": scale(raw["landslide"]["low_vegetation"]["value"], 0, 100),
        },
        "avalanche": {
            "recent_snowfall": scale(raw["avalanche"]["recent_snowfall"]["value"], 0, 80),
            "snow_depth": scale(raw["avalanche"]["snow_depth"]["value"], 0, 250),
            "slope_criticality": round(clamp(math.exp(-((slope_angle - 38) ** 2) / (2 * (10**2))) * 100), 2),
            "wind_transport": scale(raw["avalanche"]["wind_transport"]["value"], 5, 55),
            "temperature_change": scale(raw["avalanche"]["temperature_change"]["value"], 0, 18),
            "snowpack_instability": scale(raw["avalanche"]["snowpack_instability"]["value"], 0, 100),
        },
    }


def extract_raw_indicator_values(
    weather: dict[str, Any],
    flood: dict[str, Any],
    location: dict[str, Any],
    terrain: dict[str, Any] | None = None,
    external: dict[str, Any] | None = None,
) -> dict[str, dict[str, dict[str, Any]]]:
    external = external or {}
    nasa_power = external.get("nasa_power") or {}
    firms = external.get("firms") or {}
    current = weather.get("current") or {}
    daily = weather.get("daily") or []
    # Open-Meteo daily output contains 30 past days plus today and the forecast tail.
    # Drought monitoring should use observed/today values, not future dry forecast days.
    analysis_daily = daily[:-6] if weather.get("source") == "open-meteo" and len(daily) > 31 else daily
    precipitation_values = [float(day.get("precipitation") or 0) for day in analysis_daily]
    historical_precipitation = precipitation_values[-30:] if precipitation_values else []
    temperature_values = [float(day.get("temperature") or current.get("temperature_2m") or 0) for day in analysis_daily]
    historical_temperatures = temperature_values[-30:] if temperature_values else []
    maximum_temperatures = [float(day.get("temperature_max") or day.get("temperature") or current.get("temperature_2m") or 0) for day in analysis_daily]
    minimum_temperatures = [float(day.get("temperature_min") or day.get("temperature") or current.get("temperature_2m") or 0) for day in analysis_daily]
    snowfall_values = [float(day.get("snowfall") or 0) for day in analysis_daily]
    dry_days = _consecutive_dry_days(historical_precipitation)
    current_precipitation = float(current.get("precipitation") or 0)
    total_precipitation_7d = sum(historical_precipitation[-7:]) if historical_precipitation else float(current.get("precipitation") or 0)
    total_precipitation_30d = (
        sum(historical_precipitation[-30:])
        if historical_precipitation
        else float(nasa_power.get("precipitation_30d_mm") or current.get("precipitation") or 0)
    )
    max_precipitation = max(precipitation_values, default=float(current.get("precipitation") or 0))
    avg_temp = mean(historical_temperatures[-7:]) if historical_temperatures else float(nasa_power.get("temperature_30d_mean_c") or current.get("temperature_2m") or 0)
    max_temp = max(maximum_temperatures[-7:], default=avg_temp)
    night_temp = min(minimum_temperatures[-7:], default=avg_temp)
    river_values = (flood.get("daily") or {}).get("river_discharge") or []
    river_discharge = max([float(value or 0) for value in river_values], default=0)
    discharge_expected_values = (
        (flood.get("daily") or {}).get("river_discharge_p75")
        or (flood.get("daily") or {}).get("river_discharge_mean")
        or (flood.get("daily") or {}).get("river_discharge_median")
        or []
    )
    expected_discharge_numbers = [float(value or 0) for value in discharge_expected_values if value is not None]
    expected_discharge = mean(expected_discharge_numbers) if expected_discharge_numbers else 0
    discharge_anomaly = (river_discharge / expected_discharge * 100) if expected_discharge > 0 else river_discharge
    humidity = float(current.get("relative_humidity_2m") or 50)
    wind = float(current.get("wind_speed_10m") or 0)
    wind_gusts = float(current.get("wind_gusts_10m") or wind)
    apparent = float(current.get("apparent_temperature") or current.get("temperature_2m") or 0)
    snow_depth = float(current.get("snow_depth") or 0)
    if weather.get("source") == "open-meteo":
        # Open-Meteo reports snow depth in meters. The avalanche formula uses cm.
        snow_depth *= 100
    recent_snowfall = max(float(current.get("recent_snowfall") or 0), sum(snowfall_values[-2:]) if snowfall_values else 0)
    temp_change = abs((historical_temperatures[-1] if historical_temperatures else avg_temp) - (historical_temperatures[0] if historical_temperatures else avg_temp))
    terrain = terrain or {}
    slope_angle = float(terrain.get("slope_degrees") or location.get("slope_index", 40) * 0.55)
    elevation = float(terrain.get("elevation_m") or _mock_elevation(location))

    soil_moisture, soil_source = _soil_moisture_index(current, nasa_power, total_precipitation_7d, humidity)
    soil_moisture_deficit = round(clamp(100 - soil_moisture), 2)
    base_precipitation_deficit = clamp(100 - scale(total_precipitation_30d, 20, 160))
    recent_rain_relief = max(scale(total_precipitation_7d, 10, 55), scale(current_precipitation, 1, 18))
    precipitation_deficit = round(clamp(base_precipitation_deficit - recent_rain_relief * 1.1), 2)
    rain_adjusted_dry_days = round(clamp(dry_days - min(10, total_precipitation_7d / 5) - (3 if current_precipitation >= 1 else 0), 0, 30), 1)
    vapor_pressure_deficit = current.get("vapor_pressure_deficit")
    evapotranspiration = current.get("et0_fao_evapotranspiration")
    vpd_stress = scale(float(vapor_pressure_deficit or 0), 0.4, 4.0) if vapor_pressure_deficit is not None else 0
    et0_stress = scale(float(evapotranspiration or 0), 0, 8) if evapotranspiration is not None else 0
    dryness = round(max(scale(avg_temp, 15, 42), scale(100 - humidity, 20, 85), scale(dry_days, 0, 10), vpd_stress, et0_stress), 2)
    temperature_anomaly = max(0, avg_temp - _regional_baseline_temp(location))
    hot_days = sum(1 for value in maximum_temperatures[-7:] if value >= 30)
    low_vegetation = round(clamp(100 - float(location.get("vegetation_index", 50))), 2)
    active_fire_proximity = float(firms.get("active_fire_proximity") or 0)

    return {
        "flood": {
            "rainfall": {"value": round(total_precipitation_7d, 2), "unit": "mm / 7 days"},
            "discharge_anomaly": {"value": round(discharge_anomaly, 2), "unit": "% of expected discharge" if expected_discharge > 0 else "m3/s"},
            "soil_moisture": {"value": soil_moisture, "unit": soil_source},
            "low_elevation": {"value": round(elevation, 1), "unit": "m"},
        },
        "wildfire": {
            "temperature": {"value": round(avg_temp, 1), "unit": "C"},
            "wind": {"value": round(max(wind, wind_gusts * 0.7), 1), "unit": "km/h wind/gust proxy"},
            "dryness": {"value": dryness, "unit": "prototype index"},
            "precipitation_deficit": {"value": precipitation_deficit, "unit": "30-day deficit index"},
            "active_fire_proximity": {"value": active_fire_proximity, "unit": firms.get("source", "not configured")},
        },
        "drought": {
            "precipitation_deficit": {"value": precipitation_deficit, "unit": "30-day deficit index"},
            "precipitation_30d": {"value": round(total_precipitation_30d, 2), "unit": "mm / 30 days"},
            "recent_precipitation_7d": {"value": round(total_precipitation_7d, 2), "unit": "mm / 7 days"},
            "current_precipitation": {"value": round(current_precipitation, 2), "unit": "mm current"},
            "soil_moisture_deficit": {"value": soil_moisture_deficit, "unit": f"deficit from {soil_source}"},
            "temperature_anomaly": {"value": round(temperature_anomaly, 1), "unit": "C above baseline"},
            "dry_days": {"value": rain_adjusted_dry_days, "unit": "rain-adjusted days"},
        },
        "heatwave": {
            "max_temperature_anomaly": {"value": round(max(0, max_temp - 30), 1), "unit": "C above 30"},
            "night_temperature_anomaly": {"value": round(max(0, night_temp - 20), 1), "unit": "C above 20"},
            "consecutive_hot_days": {"value": hot_days, "unit": "days"},
            "apparent_temperature": {"value": round(apparent, 1), "unit": "C"},
        },
        "landslide": {
            "rainfall_intensity": {"value": round(max_precipitation, 2), "unit": "mm/day"},
            "antecedent_rainfall": {"value": round(total_precipitation_7d, 2), "unit": "mm / 7 days"},
            "slope": {"value": round(slope_angle, 1), "unit": "degrees"},
            "soil_moisture": {"value": soil_moisture, "unit": soil_source},
            "low_vegetation": {"value": low_vegetation, "unit": "prototype index"},
        },
        "avalanche": {
            "recent_snowfall": {"value": round(recent_snowfall, 1), "unit": "cm estimate"},
            "snow_depth": {"value": round(snow_depth, 1), "unit": "cm"},
            "slope_criticality": {"value": round(slope_angle, 1), "unit": "degrees"},
            "wind_transport": {"value": round(max(wind, wind_gusts * 0.7), 1), "unit": "km/h wind/gust proxy"},
            "temperature_change": {"value": round(temp_change, 1), "unit": "C"},
            "snowpack_instability": {"value": float(location.get("snowpack_instability", 40)), "unit": "prototype index"},
        },
    }


def normalize_earthquake_indicators(
    earthquake: dict[str, Any] | None,
    location: dict[str, Any],
    external: dict[str, Any] | None = None,
) -> dict[str, float]:
    raw = extract_raw_earthquake_values(earthquake, location, external)
    return {
        "magnitude_index": scale(raw["magnitude_index"]["value"], 3.0, 8.0),
        "shallow_depth": scale(raw["shallow_depth"]["value"], 250, 0),
        "distance_decay": round(clamp(math.exp(-(raw["distance_decay"]["value"] / 100)) * 100), 2),
        "exposure": float(raw["exposure"]["value"]),
    }


def extract_raw_earthquake_values(
    earthquake: dict[str, Any] | None,
    location: dict[str, Any],
    external: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    external = external or {}
    worldpop = external.get("worldpop") or {}
    exposure = float(worldpop.get("exposure_index") or location.get("exposure_index", 50))
    exposure_unit = "WorldPop density-derived index" if worldpop.get("source") == "worldpop" else "prototype index"
    if not earthquake:
        return {
            "magnitude_index": {"value": 0, "unit": "Mw"},
            "shallow_depth": {"value": 250, "unit": "km"},
            "distance_decay": {"value": 1000, "unit": "km"},
            "exposure": {"value": exposure, "unit": exposure_unit},
        }

    distance_km = haversine(
        float(location["lat"]),
        float(location["lon"]),
        float(earthquake.get("lat") or 0),
        float(earthquake.get("lon") or 0),
    )
    return {
        "magnitude_index": {"value": float(earthquake.get("magnitude") or 0), "unit": "Mw"},
        "shallow_depth": {"value": float(earthquake.get("depth") or 0), "unit": "km"},
        "distance_decay": {"value": round(distance_km, 1), "unit": "km"},
        "exposure": {"value": exposure, "unit": exposure_unit},
    }


def nearest_earthquake(
    earthquakes: list[dict[str, Any]],
    location: dict[str, Any],
) -> dict[str, Any] | None:
    if not earthquakes:
        return None
    return min(
        earthquakes,
        key=lambda quake: haversine(
            float(location["lat"]),
            float(location["lon"]),
            float(quake.get("lat") or 0),
            float(quake.get("lon") or 0),
        ),
    )


def _soil_moisture_index(
    current: dict[str, Any],
    nasa_power: dict[str, Any],
    total_precipitation_7d: float,
    humidity: float,
) -> tuple[float, str]:
    open_meteo_values = [
        current.get("soil_moisture_0_to_1cm"),
        current.get("soil_moisture_1_to_3cm"),
        current.get("soil_moisture_3_to_9cm"),
        current.get("soil_moisture_9_to_27cm"),
    ]
    soil_values = []
    for value in open_meteo_values:
        try:
            if value is not None:
                soil_values.append(float(value))
        except (TypeError, ValueError):
            continue
    if soil_values:
        return round(scale(mean(soil_values), 0.05, 0.45), 2), "Open-Meteo soil moisture index"

    power_values = [
        nasa_power.get("soil_wetness_top_mean"),
        nasa_power.get("soil_wetness_root_mean"),
    ]
    power_soil_values = []
    for value in power_values:
        try:
            if value is not None:
                power_soil_values.append(float(value))
        except (TypeError, ValueError):
            continue
    if power_soil_values:
        return round(scale(mean(power_soil_values), 0.05, 0.50), 2), "NASA POWER soil wetness index"

    estimated = clamp(scale(total_precipitation_7d, 5, 90) * 0.75 + scale(humidity, 30, 95) * 0.25)
    return round(estimated, 2), "rainfall/humidity fallback index"


def _consecutive_dry_days(precipitation_values: list[float]) -> int:
    count = 0
    for value in reversed(precipitation_values):
        if float(value or 0) >= 1:
            break
        count += 1
    return count


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    from math import asin, cos, radians, sin, sqrt

    earth_radius_km = 6371
    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)
    a = sin(d_lat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
    return earth_radius_km * 2 * asin(sqrt(a))


def _regional_baseline_temp(location: dict[str, Any]) -> float:
    if "baseline_temperature" in location:
        return float(location["baseline_temperature"])
    return {
        "md-moldova": 22,
        "ro-romania": 21,
        "it-italy": 24,
        "jp-japan": 23,
        "np-nepal": 20,
        "at-austria": 15,
        "gr-greece": 25,
        "tr-turkey": 23,
        "es-spain": 25,
        "fr-france": 20,
        "de-germany": 18,
        "pl-poland": 18,
        "ua-ukraine": 20,
        "us-california": 25,
    }.get(location.get("id"), 22)


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


def _active_fire_index(location_id: str) -> float:
    return {
        "gr-greece": 32,
        "tr-turkey": 36,
        "es-spain": 34,
        "it-italy": 30,
        "us-california": 68,
        "np-nepal": 18,
        "at-austria": 8,
    }.get(location_id, 12)
