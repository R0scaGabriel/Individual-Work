from __future__ import annotations

import json
import math
import platform
import subprocess
from pathlib import Path
from typing import Any

from .calibration import calibrate_probability


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


def calculate_risk(
    disaster_type: str,
    indicators: dict[str, Any],
    raw_values: dict[str, dict[str, Any]] | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    disaster_type = disaster_type.lower()
    if disaster_type not in ENGINE_ARGUMENTS:
        raise ValueError(f"Unsupported disaster type: {disaster_type}")

    context = context or {}
    raw_values = raw_values or {}
    ordered_keys = ENGINE_ARGUMENTS[disaster_type]
    values = [float(indicators.get(key, 0)) for key in ordered_keys]
    engine_output = _run_c_engine(disaster_type, values)
    if engine_output:
        raw_hazard = float(engine_output.get("hazard_index", float(engine_output.get("risk_score", 0)) / 100))
        calculation_engine = "c"
    else:
        raw_hazard = _hazard_unit(disaster_type, values)
        calculation_engine = "python_fallback"

    evidence_gate = _evidence_gate(disaster_type, values, raw_values)
    if evidence_gate.get("triggered") and evidence_gate.get("hazard_cap") is not None:
        raw_hazard = min(raw_hazard, float(evidence_gate["hazard_cap"]))
    calibration = calibrate_probability(
        disaster_type,
        raw_hazard,
        {
            **context,
            "evidence_gate": evidence_gate,
        },
    )
    severity_score = _severity_score(disaster_type, values)
    exposure_vulnerability = _exposure_vulnerability_factor(disaster_type, values, context)
    overall_risk_score = calibration["probability"] * severity_score * exposure_vulnerability
    if evidence_gate.get("triggered"):
        overall_risk_score = min(overall_risk_score, float(evidence_gate.get("overall_cap", 25)))
    overall_risk_score = round(max(0, min(100, overall_risk_score)), 2)
    level = risk_level(overall_risk_score)
    confidence = _confidence_label(disaster_type, values, raw_values, context, evidence_gate)

    normalized_indicators = {key: round(value, 2) for key, value in zip(ordered_keys, values)}
    explanation = _interpreted_explanation(
        disaster_type,
        level,
        normalized_indicators,
        calibration["chance_percent"],
        severity_score,
        evidence_gate,
    )

    return {
        "disaster": disaster_type,
        "disaster_type": disaster_type,
        "applicable": context.get("applicable", True),
        "chance_percent": calibration["chance_percent"],
        "time_window_days": calibration["time_window_days"],
        "event_definition": calibration["event_definition"],
        "severity_score": round(severity_score, 2),
        "overall_risk_score": overall_risk_score,
        # Backward-compatible aliases used by the current frontend/map code.
        "risk_score": overall_risk_score,
        "probability": round(calibration["probability"], 4),
        "risk_level": level,
        "confidence": confidence,
        "raw_hazard": round(raw_hazard, 4),
        "hazard_index": round(raw_hazard, 4),
        "exposure_vulnerability": round(exposure_vulnerability, 3),
        "calibration_method": calibration["calibration_method"],
        "calibration_note": calibration["calibration_note"],
        "evidence_gate": evidence_gate,
        "calculation_engine": calculation_engine,
        "model_family": MODEL_FAMILIES[disaster_type],
        "indicators": normalized_indicators,
        "explanation": explanation,
        "recommendation": RECOMMENDATIONS[level],
    }


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


def _raw_number(raw_values: dict[str, dict[str, Any]], key: str, default: float = 0.0) -> float:
    try:
        return float((raw_values.get(key) or {}).get("value", default) or default)
    except (TypeError, ValueError):
        return default


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
        hazard = _clamp_unit(0.45 * runoff_ratio + 0.25 * discharge + 0.20 * soil + 0.10 * low)
        if rain < 0.18 and discharge < 0.20:
            hazard = min(hazard, 0.24)
        return hazard

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
        hazard = _clamp_unit(0.55 * fire_weather_proxy + 0.15 * temperature + 0.20 * precipitation_deficit + 0.10 * active_fire)
        if dryness < 0.25 and active_fire < 0.20:
            hazard = min(hazard, 0.24)
        return hazard

    if disaster_type == "drought":
        precipitation_deficit, soil_deficit, temperature_anomaly, dry_days = [_unit(value) for value in values]
        spei_like = _clamp_unit(0.65 * precipitation_deficit + 0.35 * temperature_anomaly)
        combined_deficit = math.sqrt(precipitation_deficit * soil_deficit)
        hazard = _clamp_unit(0.35 * precipitation_deficit + 0.25 * spei_like + 0.25 * combined_deficit + 0.15 * dry_days)
        if dry_days < 0.10 and precipitation_deficit < 0.60:
            hazard = min(hazard, 0.24)
        if precipitation_deficit < 0.25 and dry_days < 0.20:
            hazard = min(hazard, 0.18)
        return hazard

    if disaster_type == "heatwave":
        max_anomaly, night_anomaly, consecutive_hot_days, apparent_temperature = [_unit(value) for value in values]
        excess_heat_factor = _clamp_unit(max_anomaly * (0.45 + 0.35 * consecutive_hot_days + 0.20 * night_anomaly))
        heat_index_proxy = _clamp_unit(0.60 * apparent_temperature + 0.25 * night_anomaly + 0.15 * max_anomaly)
        hazard = _clamp_unit(0.55 * excess_heat_factor + 0.30 * heat_index_proxy + 0.15 * consecutive_hot_days)
        if consecutive_hot_days < 0.25 and max_anomaly < 0.45:
            hazard = min(hazard, 0.24)
        return hazard

    if disaster_type == "landslide":
        intensity, antecedent, slope, soil, low_vegetation = [_unit(value) for value in values]
        driving = 0.45 * slope + 0.25 * soil + 0.20 * antecedent + 0.10 * intensity
        resistance = 0.30 + 0.30 * (1 - low_vegetation) + 0.25 * (1 - soil) + 0.15 * (1 - slope)
        infinite_slope_instability = _logistic_unit(driving - resistance, 7, 0)
        intensity_duration_proxy = _clamp_unit(intensity * ((0.15 + antecedent) ** 0.55))
        hazard = _clamp_unit(0.62 * infinite_slope_instability + 0.38 * intensity_duration_proxy)
        if intensity < 0.20 and antecedent < 0.25:
            hazard = min(hazard, 0.24)
        return hazard

    if disaster_type == "avalanche":
        snowfall, snow_depth, slope, wind, temperature_change, weak_layer = [_unit(value) for value in values]
        load = 0.35 * snowfall + 0.25 * snow_depth + 0.18 * wind + 0.12 * temperature_change + 0.10 * weak_layer
        strength = 0.45 * (1 - weak_layer) + 0.25 * (1 - temperature_change) + 0.20 * (1 - wind) + 0.10 * snow_depth
        stability_index = strength / (load + 0.08)
        stability_failure = _clamp_unit((1.55 - stability_index) / 1.55)
        propagation_proxy = _clamp_unit(slope * (0.45 * snow_depth + 0.35 * snowfall + 0.20 * wind))
        hazard = _clamp_unit(0.65 * stability_failure + 0.35 * propagation_proxy)
        if snowfall < 0.15 and snow_depth < 0.15:
            hazard = min(hazard, 0.20)
        return hazard

    return 0.0


def _python_formula_fallback(disaster_type: str, values: list[float]) -> dict[str, Any]:
    hazard_unit = _hazard_unit(disaster_type, values)
    risk_score = hazard_unit * 100
    return {
        "risk_score": round(risk_score, 2),
        "probability": round(hazard_unit, 4),
        "risk_level": risk_level(risk_score),
        "hazard_index": round(hazard_unit, 4),
    }


def _severity_score(disaster_type: str, values: list[float]) -> float:
    units = [_unit(value) for value in values]
    if disaster_type == "flood":
        rain, discharge, soil, low = units
        severity = 0.30 * discharge + 0.25 * low + 0.25 * rain + 0.20 * soil
    elif disaster_type == "earthquake":
        magnitude, shallow, _distance, exposure = units
        severity = 0.50 * magnitude + 0.25 * shallow + 0.25 * exposure
    elif disaster_type == "wildfire":
        temperature, wind, dryness, precipitation_deficit, active_fire = units
        severity = 0.20 * temperature + 0.30 * wind + 0.25 * dryness + 0.15 * precipitation_deficit + 0.10 * active_fire
    elif disaster_type == "drought":
        precipitation_deficit, soil_deficit, temperature_anomaly, dry_days = units
        severity = 0.30 * precipitation_deficit + 0.35 * soil_deficit + 0.20 * temperature_anomaly + 0.15 * dry_days
    elif disaster_type == "heatwave":
        max_anomaly, night_anomaly, consecutive_hot_days, apparent = units
        severity = 0.30 * max_anomaly + 0.25 * night_anomaly + 0.15 * consecutive_hot_days + 0.30 * apparent
    elif disaster_type == "landslide":
        intensity, antecedent, slope, soil, low_vegetation = units
        severity = 0.20 * intensity + 0.20 * antecedent + 0.30 * slope + 0.20 * soil + 0.10 * low_vegetation
    elif disaster_type == "avalanche":
        snowfall, snow_depth, slope, wind, temperature_change, weak_layer = units
        severity = 0.20 * snowfall + 0.25 * snow_depth + 0.25 * slope + 0.15 * wind + 0.05 * temperature_change + 0.10 * weak_layer
    else:
        severity = max(units, default=0)
    return round(max(0, min(100, severity * 100)), 2)


def _exposure_vulnerability_factor(disaster_type: str, values: list[float], context: dict[str, Any]) -> float:
    units = [_unit(value) for value in values]
    if context.get("applicable") is False:
        return 0.0
    if disaster_type == "earthquake" and len(units) >= 4:
        return 0.60 + 0.40 * units[3]
    if disaster_type == "flood" and len(units) >= 4:
        return 0.75 + 0.25 * units[3]
    if disaster_type in {"landslide", "avalanche"} and len(units) >= 3:
        return 0.80 + 0.20 * units[2]
    return 1.0


def _evidence_gate(
    disaster_type: str,
    values: list[float],
    raw_values: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    units = [_unit(value) for value in values]
    raw_values = raw_values or {}
    gate = {"triggered": False, "reason": "", "chance_multiplier": 1.0, "overall_cap": 100, "hazard_cap": None}

    def triggered(
        reason: str,
        chance_multiplier: float = 0.65,
        overall_cap: float = 25,
        hazard_cap: float | None = None,
    ) -> dict[str, Any]:
        return {
            "triggered": True,
            "reason": reason,
            "chance_multiplier": chance_multiplier,
            "overall_cap": overall_cap,
            "hazard_cap": hazard_cap,
        }

    if disaster_type == "flood":
        rain, discharge, *_ = units
        if rain < 0.18 and discharge < 0.20:
            return triggered("Flood trigger is weak because rainfall and river-discharge signal are both low.", 0.55, 24)
    elif disaster_type == "wildfire":
        _temperature, _wind, dryness, _precipitation_deficit, active_fire = units
        if dryness < 0.25 and active_fire < 0.20:
            return triggered("Wildfire trigger is weak because fuel dryness is low and no active-fire proximity is configured.", 0.55, 24)
    elif disaster_type == "drought":
        precipitation_deficit, _soil_deficit, _temperature_anomaly, dry_days = units
        recent_rain_7d = _raw_number(raw_values, "recent_precipitation_7d")
        if recent_rain_7d > 0:
            return triggered(
                f"Drought score is capped at Low because {recent_rain_7d:.1f} mm of rain was recorded in the last 7 days.",
                0.35,
                25,
                0.24,
            )
        if precipitation_deficit < 0.25 and dry_days < 0.20:
            return triggered("Drought trigger is weak because recent rain/dry-day evidence does not support drought development.", 0.45, 18, 0.18)
        if dry_days < 0.10 and precipitation_deficit < 0.60:
            return triggered("Drought trigger is limited because dry-day persistence is near zero and precipitation deficit is not strong.", 0.60, 24, 0.24)
    elif disaster_type == "heatwave":
        max_anomaly, _night_anomaly, hot_days, _apparent = units
        if hot_days < 0.25 and max_anomaly < 0.45:
            return triggered("Heat-wave trigger is weak because heat has not persisted and maximum-temperature anomaly is not strong.", 0.55, 24)
    elif disaster_type == "landslide":
        intensity, antecedent, *_ = units
        if intensity < 0.20 and antecedent < 0.25:
            return triggered("Landslide trigger is weak because rainfall intensity and antecedent rainfall are both low.", 0.50, 24)
    elif disaster_type == "avalanche":
        snowfall, snow_depth, *_ = units
        if snowfall < 0.15 and snow_depth < 0.15:
            return triggered("Avalanche trigger is weak because recent snowfall and snow depth are both low.", 0.40, 20)
    elif disaster_type == "earthquake":
        magnitude, _shallow, distance_decay, _exposure = units
        if magnitude <= 0 or distance_decay < 0.02:
            return triggered("No recent significant nearby earthquake supports only low short-term impact context; exact earthquake prediction is unavailable.", 0.50, 20)
    return gate


def _confidence_label(
    disaster_type: str,
    values: list[float],
    raw_values: dict[str, dict[str, Any]],
    context: dict[str, Any],
    evidence_gate: dict[str, Any],
) -> str:
    if context.get("applicable") is False:
        return "Low"

    score = 58
    sources = [
        str(context.get("weather_source", "")),
        str(context.get("flood_source", "")),
        str((context.get("terrain") or {}).get("source", "")),
    ]
    if any(source in {"open-meteo", "open-meteo-flood", "opentopodata", "usgs"} for source in sources):
        score += 8
    if any(source in {"open-meteo-core", "nasa-power-derived", "country-metadata"} for source in sources):
        score -= 5
    if any(source in {"mock", "sample-location"} for source in sources):
        score -= 15
    if any(source == "unavailable" for source in sources):
        score -= 25

    missing = 0
    for raw in raw_values.values():
        if raw.get("value") is None or raw.get("unit") == "unavailable":
            missing += 1
    score -= missing * 6

    strong_indicators = sum(1 for value in values if float(value) >= 45)
    if strong_indicators >= 2:
        score += 10
    elif strong_indicators == 0:
        score -= 8

    if evidence_gate.get("triggered"):
        score -= 12

    if disaster_type == "earthquake":
        score += 5

    if score >= 75:
        return "High"
    if score >= 45:
        return "Moderate"
    return "Low"


def _interpreted_explanation(
    disaster_type: str,
    level: str,
    indicators: dict[str, float],
    chance_percent: float,
    severity_score: float,
    evidence_gate: dict[str, Any],
) -> str:
    leading = sorted(indicators.items(), key=lambda item: item[1], reverse=True)[:2]
    leading_text = ", ".join(f"{key.replace('_', ' ')}={value:.1f}" for key, value in leading)
    if disaster_type == "earthquake":
        prefix = (
            "This is recent-earthquake impact and aftershock-aware risk context, not exact earthquake prediction. "
            "Short-term earthquake prediction is unavailable in this prototype."
        )
    else:
        prefix = EXPLANATIONS[disaster_type]
    gate_text = f" Evidence gate: {evidence_gate['reason']}" if evidence_gate.get("triggered") else ""
    return (
        f"{prefix} Calibrated chance is {chance_percent:.1f}% for the defined time window; "
        f"severity-if-event is {severity_score:.1f}/100, producing {level} overall risk. "
        f"Strongest normalized drivers: {leading_text}.{gate_text}"
    )


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
