from __future__ import annotations

import json
import math
import platform
import subprocess
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RISK_ENGINE_DIR = PROJECT_ROOT / "risk_engine"
RISK_ENGINE_SOURCE = RISK_ENGINE_DIR / "risk_engine.c"
RISK_ENGINE_EXECUTABLE = RISK_ENGINE_DIR / ("risk_engine.exe" if platform.system() == "Windows" else "risk_engine")


ENGINE_ARGUMENTS = {
    "flood": ["rainfall", "discharge_anomaly", "soil_moisture", "low_elevation"],
    "earthquake": ["magnitude_index", "shallow_depth", "distance_decay", "exposure"],
    "wildfire": ["temperature", "wind", "dryness", "precipitation_deficit", "active_fire_proximity"],
    "drought": ["precipitation_deficit", "soil_moisture_deficit", "temperature_anomaly", "dry_days"],
    "heatwave": ["max_temperature_anomaly", "night_temperature_anomaly", "consecutive_hot_days", "apparent_temperature"],
    "landslide": ["rainfall_intensity", "antecedent_rainfall", "slope", "soil_moisture", "low_vegetation"],
    "avalanche": ["recent_snowfall", "snow_depth", "slope_criticality", "wind_transport", "temperature_change", "snowpack_instability"],
}


MODEL_FAMILIES = {
    "flood": "SCS Curve Number runoff proxy with river-discharge and saturation terms.",
    "earthquake": "Gutenberg-Richter and Omori/ETAS-inspired impact-rate proxy for recent events.",
    "wildfire": "Canadian Fire Weather Index-style proxy using ISI, BUI, and ignition context.",
    "drought": "SPI/SPEI/PDSI-inspired drought-stress proxy using precipitation, evaporation demand, and soil deficit.",
    "heatwave": "Heat Index and Excess Heat Factor-inspired proxy using anomaly, humidity stress, and persistence.",
    "landslide": "Infinite-slope factor-of-safety plus rainfall intensity-duration threshold proxy.",
    "avalanche": "Snow-slab stability-index and propagation proxy using snow, slope, wind, and weak-layer indicators.",
}


EXPLANATIONS = {
    "flood": "Flood risk estimation uses an SCS Curve Number-inspired runoff proxy, then combines runoff with river discharge, soil saturation, and low-elevation susceptibility.",
    "earthquake": "Earthquake impact-risk monitoring uses a Gutenberg-Richter and Omori/ETAS-inspired event influence proxy, not deterministic earthquake prediction.",
    "wildfire": "Wildfire risk estimation uses a Fire Weather Index-style interaction between fuel dryness, wind spread potential, buildup dryness, and ignition context.",
    "drought": "Drought risk estimation uses SPI/SPEI/PDSI-inspired drought-stress terms from precipitation deficit, evaporation demand, soil deficit, and persistence.",
    "heatwave": "Heat wave risk estimation uses Heat Index and Excess Heat Factor ideas: anomalous heat, warm nights, apparent temperature, and persistence.",
    "landslide": "Landslide risk estimation uses a simplified infinite-slope stability proxy plus rainfall intensity-duration triggering.",
    "avalanche": "Avalanche risk estimation uses a simplified snow-slab stability-index and propagation proxy from snow load, slope criticality, wind, temperature change, and weak-layer susceptibility.",
}


INDICATOR_EXPLANATIONS = {
    "flood": {
        "rainfall": "Recent rainfall is used because high precipitation can quickly increase runoff and flood potential.",
        "discharge_anomaly": "River discharge anomaly is used because unusually high water volume in the channel can increase flood risk.",
        "soil_moisture": "Soil moisture is used because saturated soil absorbs less rain and produces more surface runoff.",
        "low_elevation": "Low elevation is used because low-lying areas are more likely to collect or receive floodwater.",
    },
    "earthquake": {
        "magnitude_index": "Magnitude index is used because larger earthquakes release more energy and can cause stronger shaking.",
        "shallow_depth": "Shallow depth is used because shallow events usually transfer more shaking to the surface.",
        "distance_decay": "Distance decay is used because shaking impact usually decreases with distance from the epicenter.",
        "exposure": "Exposure is used to represent the people, buildings, and infrastructure that could be affected.",
    },
    "wildfire": {
        "temperature": "Temperature is used because heat dries fuels and can increase fire spread potential.",
        "wind": "Wind is used because stronger wind can accelerate fire spread and transport embers.",
        "dryness": "Dryness is used because low humidity and dry fuels make ignition and spread more likely.",
        "precipitation_deficit": "Precipitation deficit is used because long dry periods reduce fuel moisture.",
        "active_fire_proximity": "Active-fire proximity is used as a prototype indicator of nearby ignition context.",
    },
    "drought": {
        "precipitation_deficit": "Precipitation deficit is used because below-normal rainfall is a primary drought driver.",
        "soil_moisture_deficit": "Soil moisture deficit is used because dry soils indicate water stress in the land surface.",
        "temperature_anomaly": "Temperature anomaly is used because unusual heat increases evaporation and water demand.",
        "dry_days": "Dry days are used because persistent rain-free periods can intensify drought conditions.",
    },
    "heatwave": {
        "max_temperature_anomaly": "Maximum temperature anomaly is used because unusually hot days increase heat stress.",
        "night_temperature_anomaly": "Night temperature anomaly is used because warm nights reduce recovery time for people and ecosystems.",
        "consecutive_hot_days": "Consecutive hot days are used because heat impacts increase when extreme heat persists.",
        "apparent_temperature": "Apparent temperature is used because humidity and heat together affect perceived heat stress.",
    },
    "landslide": {
        "rainfall_intensity": "Rainfall intensity is used because intense rain can rapidly destabilize slopes.",
        "antecedent_rainfall": "Antecedent rainfall is used because prior rain can keep soils saturated before a triggering storm.",
        "slope": "Slope is used because steeper terrain is generally more susceptible to mass movement.",
        "soil_moisture": "Soil moisture is used because saturated soils lose strength and can become unstable.",
        "low_vegetation": "Low vegetation is used because less root reinforcement can increase slope instability.",
    },
    "avalanche": {
        "recent_snowfall": "Recent snowfall is used because new snow can overload weak layers in the snowpack.",
        "snow_depth": "Snow depth is used because deeper snowpacks can store more unstable slab material.",
        "slope_criticality": "Slope criticality is used because avalanche release is most common near a critical slope-angle range.",
        "wind_transport": "Wind transport is used because wind can form unstable snow slabs on leeward slopes.",
        "temperature_change": "Temperature change is used because rapid warming or cooling can affect snowpack stability.",
        "snowpack_instability": "Snowpack instability is a prototype terrain/location factor representing weak-layer susceptibility.",
    },
}


INDICATOR_LABELS = {
    "rainfall": "Rainfall",
    "discharge_anomaly": "Discharge anomaly",
    "soil_moisture": "Soil moisture",
    "low_elevation": "Low elevation",
    "magnitude_index": "Magnitude index",
    "shallow_depth": "Shallow depth",
    "distance_decay": "Distance decay",
    "exposure": "Exposure",
    "temperature": "Temperature",
    "wind": "Wind",
    "dryness": "Dryness",
    "precipitation_deficit": "Precipitation deficit",
    "active_fire_proximity": "Active-fire proximity",
    "soil_moisture_deficit": "Soil moisture deficit",
    "temperature_anomaly": "Temperature anomaly",
    "dry_days": "Dry days",
    "max_temperature_anomaly": "Max temperature anomaly",
    "night_temperature_anomaly": "Night temperature anomaly",
    "consecutive_hot_days": "Consecutive hot days",
    "apparent_temperature": "Apparent temperature",
    "rainfall_intensity": "Rainfall intensity",
    "antecedent_rainfall": "Antecedent rainfall",
    "slope": "Slope",
    "low_vegetation": "Low vegetation",
    "recent_snowfall": "Recent snowfall",
    "snow_depth": "Snow depth",
    "slope_criticality": "Slope criticality",
    "wind_transport": "Wind transport",
    "temperature_change": "Temperature change",
    "snowpack_instability": "Snowpack instability",
}


RECOMMENDATIONS = {
    "Low": "Continue routine monitoring and compare trends with historical local records.",
    "Medium": "Review recent indicator changes and prepare a targeted field or data check.",
    "High": "Increase observation frequency and validate the estimate with regional experts or official bulletins.",
    "Critical": "Treat this as a prototype alert: verify with official agencies before any operational decision.",
}


def calculate_risk(disaster_type: str, indicators: dict[str, Any]) -> dict[str, Any]:
    disaster_type = disaster_type.lower()
    if disaster_type not in ENGINE_ARGUMENTS:
        raise ValueError(f"Unsupported disaster type: {disaster_type}")

    ordered_keys = ENGINE_ARGUMENTS[disaster_type]
    values = [float(indicators.get(key, 0)) for key in ordered_keys]
    engine_output = _run_c_engine(disaster_type, values)
    if engine_output:
        result = engine_output
        result["calculation_engine"] = "c"
    else:
        result = _python_formula_fallback(disaster_type, values)
        result["calculation_engine"] = "python_fallback"

    result["disaster_type"] = disaster_type
    result["model_family"] = MODEL_FAMILIES[disaster_type]
    result["indicators"] = {key: round(value, 2) for key, value in zip(ordered_keys, values)}
    result["explanation"] = _explain(disaster_type, result["risk_level"], result["indicators"])
    result["recommendation"] = RECOMMENDATIONS[result["risk_level"]]
    return result


def build_indicator_details(
    disaster_type: str,
    indicators: dict[str, float],
    raw_values: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    raw_values = raw_values or {}
    explanations = INDICATOR_EXPLANATIONS.get(disaster_type, {})
    details = []
    for key in ENGINE_ARGUMENTS.get(disaster_type, indicators.keys()):
        raw = raw_values.get(key, {})
        details.append(
            {
                "key": key,
                "label": INDICATOR_LABELS.get(key, key.replace("_", " ").title()),
                "value": raw.get("value", indicators.get(key, 0)),
                "unit": raw.get("unit", "normalized index"),
                "normalized_value": round(float(indicators.get(key, 0)), 2),
                "explanation": explanations.get(key, "This indicator contributes to the prototype risk formula."),
            }
        )
    return details


def _run_c_engine(disaster_type: str, values: list[float]) -> dict[str, Any] | None:
    if not RISK_ENGINE_EXECUTABLE.exists():
        _try_compile_engine()
    if not RISK_ENGINE_EXECUTABLE.exists():
        return None

    command = [str(RISK_ENGINE_EXECUTABLE), disaster_type, *[f"{value:.4f}" for value in values]]
    try:
        completed = subprocess.run(
            command,
            cwd=RISK_ENGINE_DIR,
            check=True,
            capture_output=True,
            text=True,
            timeout=4,
        )
        return json.loads(completed.stdout.strip())
    except Exception:
        return None


def _try_compile_engine() -> None:
    command = ["gcc", str(RISK_ENGINE_SOURCE), "-o", str(RISK_ENGINE_EXECUTABLE), "-lm"]
    try:
        subprocess.run(command, cwd=RISK_ENGINE_DIR, check=True, capture_output=True, text=True, timeout=8)
    except Exception:
        try:
            subprocess.run(command[:-1], cwd=RISK_ENGINE_DIR, check=True, capture_output=True, text=True, timeout=8)
        except Exception:
            return


def _unit(value: float) -> float:
    return max(0.0, min(100.0, float(value))) / 100.0


def _clamp_unit(value: float) -> float:
    return max(0.0, min(1.0, value))


def _saturating(value: float) -> float:
    if value <= 0:
        return 0.0
    return _clamp_unit(1 - math.exp(-value))


def _logistic_unit(value: float, steepness: float, center: float) -> float:
    return 1 / (1 + math.exp(-steepness * (value - center)))


def _hazard_unit(disaster_type: str, values: list[float]) -> float:
    if disaster_type == "flood":
        rain, discharge, soil, low = [_unit(value) for value in values]
        precipitation_mm = 5 + rain * 115
        curve_number = max(35, min(98, 55 + soil * 32 + low * 10 + discharge * 3))
        storage = (25400 / curve_number) - 254
        runoff_mm = 0.0
        if precipitation_mm > 0.2 * storage:
            runoff_mm = ((precipitation_mm - 0.2 * storage) ** 2) / (precipitation_mm + 0.8 * storage)
        runoff_ratio = _clamp_unit(runoff_mm / max(1, precipitation_mm))
        return _clamp_unit(0.45 * runoff_ratio + 0.25 * discharge + 0.20 * soil + 0.10 * low)

    if disaster_type == "earthquake":
        magnitude_index, shallow_depth, distance_decay, exposure = [_unit(value) for value in values]
        magnitude = 3 + magnitude_index * 5
        productivity = ((10 ** (0.45 * (magnitude - 3))) - 1) / ((10 ** (0.45 * 5)) - 1)
        conditional_rate = productivity * (0.25 + 0.75 * shallow_depth) * max(0.03, distance_decay)
        return _clamp_unit(_saturating(3 * conditional_rate) * (0.65 + 0.35 * exposure))

    if disaster_type == "wildfire":
        temperature, wind, dryness, precipitation_deficit, active_fire = [_unit(value) for value in values]
        initial_spread_index = dryness * (0.35 + 1.65 * wind)
        buildup_index = 0.60 * dryness + 0.40 * precipitation_deficit
        fire_weather_proxy = _saturating(1.7 * initial_spread_index * buildup_index)
        return _clamp_unit(0.55 * fire_weather_proxy + 0.15 * temperature + 0.20 * precipitation_deficit + 0.10 * active_fire)

    if disaster_type == "drought":
        precipitation_deficit, soil_deficit, temperature_anomaly, dry_days = [_unit(value) for value in values]
        spei_like = _clamp_unit(0.65 * precipitation_deficit + 0.35 * temperature_anomaly)
        return _clamp_unit(0.35 * precipitation_deficit + 0.25 * spei_like + 0.25 * soil_deficit + 0.15 * dry_days)

    if disaster_type == "heatwave":
        max_anomaly, night_anomaly, consecutive_hot_days, apparent_temperature = [_unit(value) for value in values]
        excess_heat_factor = _clamp_unit(max_anomaly * (0.45 + 0.35 * consecutive_hot_days + 0.20 * night_anomaly))
        heat_index_proxy = _clamp_unit(0.60 * apparent_temperature + 0.25 * night_anomaly + 0.15 * max_anomaly)
        return _clamp_unit(0.55 * excess_heat_factor + 0.30 * heat_index_proxy + 0.15 * consecutive_hot_days)

    if disaster_type == "landslide":
        intensity, antecedent, slope, soil, low_vegetation = [_unit(value) for value in values]
        driving = 0.45 * slope + 0.25 * soil + 0.20 * antecedent + 0.10 * intensity
        resistance = 0.30 + 0.30 * (1 - low_vegetation) + 0.25 * (1 - soil) + 0.15 * (1 - slope)
        infinite_slope_instability = _logistic_unit(driving - resistance, 7, 0)
        intensity_duration_proxy = _clamp_unit(intensity * ((0.15 + antecedent) ** 0.55))
        return _clamp_unit(0.62 * infinite_slope_instability + 0.38 * intensity_duration_proxy)

    if disaster_type == "avalanche":
        snowfall, snow_depth, slope, wind, temperature_change, weak_layer = [_unit(value) for value in values]
        load = 0.35 * snowfall + 0.25 * snow_depth + 0.18 * wind + 0.12 * temperature_change + 0.10 * weak_layer
        strength = 0.45 * (1 - weak_layer) + 0.25 * (1 - temperature_change) + 0.20 * (1 - wind) + 0.10 * snow_depth
        stability_index = strength / (load + 0.08)
        stability_failure = _clamp_unit((1.55 - stability_index) / 1.55)
        propagation_proxy = _clamp_unit(slope * (0.45 * snow_depth + 0.35 * snowfall + 0.20 * wind))
        return _clamp_unit(0.65 * stability_failure + 0.35 * propagation_proxy)

    return 0.0


def _python_formula_fallback(disaster_type: str, values: list[float]) -> dict[str, Any]:
    hazard_unit = _hazard_unit(disaster_type, values)
    risk_score = hazard_unit * 100
    probability = 1 / (1 + math.exp(-(12 * (hazard_unit - 0.50))))
    return {
        "risk_score": round(risk_score, 2),
        "probability": round(probability, 4),
        "risk_level": risk_level(risk_score),
        "hazard_index": round(hazard_unit, 4),
    }


def risk_level(risk_score: float) -> str:
    if risk_score <= 25:
        return "Low"
    if risk_score <= 50:
        return "Medium"
    if risk_score <= 75:
        return "High"
    return "Critical"


def _explain(disaster_type: str, level: str, indicators: dict[str, float]) -> str:
    leading = sorted(indicators.items(), key=lambda item: item[1], reverse=True)[:2]
    leading_text = ", ".join(f"{key.replace('_', ' ')}={value:.1f}" for key, value in leading)
    return (
        f"{EXPLANATIONS[disaster_type]} Model family: {MODEL_FAMILIES[disaster_type]} "
        f"Current prototype level is {level}; strongest normalized drivers: {leading_text}."
    )
