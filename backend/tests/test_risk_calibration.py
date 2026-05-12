from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.map_data_service import _applicability_for_cell
from services.risk_service import calculate_risk


def test_no_rain_high_soil_moisture_does_not_create_high_flood_chance() -> None:
    result = calculate_risk(
        "flood",
        {"rainfall": 0, "discharge_anomaly": 0, "soil_moisture": 85, "low_elevation": 80},
    )
    assert result["chance_percent"] <= 10
    assert result["overall_risk_score"] <= 25


def test_recent_rain_and_zero_dry_days_reduce_drought_chance() -> None:
    result = calculate_risk(
        "drought",
        {"precipitation_deficit": 20, "soil_moisture_deficit": 60, "temperature_anomaly": 0, "dry_days": 0},
    )
    assert result["chance_percent"] <= 10
    assert result["risk_level"] == "Low"


def test_one_hot_day_does_not_create_high_heatwave_risk() -> None:
    result = calculate_risk(
        "heatwave",
        {"max_temperature_anomaly": 70, "night_temperature_anomaly": 0, "consecutive_hot_days": 14, "apparent_temperature": 70},
    )
    assert result["overall_risk_score"] < 26


def test_steep_terrain_without_rainfall_does_not_create_high_landslide_risk() -> None:
    result = calculate_risk(
        "landslide",
        {"rainfall_intensity": 0, "antecedent_rainfall": 0, "slope": 90, "soil_moisture": 60, "low_vegetation": 60},
    )
    assert result["chance_percent"] <= 5
    assert result["overall_risk_score"] <= 25


def test_no_snow_makes_avalanche_not_applicable() -> None:
    raw = {
        "snow_depth": {"value": 0},
        "recent_snowfall": {"value": 0},
        "slope_criticality": {"value": 35},
    }
    applicability = _applicability_for_cell(
        "avalanche",
        {"lat": 0, "lon": 0, "cell_size_km": 1},
        raw,
        {},
        {"terrain": {"elevation_m": 1200}},
    )
    assert applicability["applicable"] is False


def test_earthquake_does_not_claim_exact_prediction() -> None:
    result = calculate_risk(
        "earthquake",
        {"magnitude_index": 0, "shallow_depth": 0, "distance_decay": 0, "exposure": 50},
    )
    assert result["chance_percent"] <= 2
    assert "prediction" in result["explanation"].lower()


if __name__ == "__main__":
    test_no_rain_high_soil_moisture_does_not_create_high_flood_chance()
    test_recent_rain_and_zero_dry_days_reduce_drought_chance()
    test_one_hot_day_does_not_create_high_heatwave_risk()
    test_steep_terrain_without_rainfall_does_not_create_high_landslide_risk()
    test_no_snow_makes_avalanche_not_applicable()
    test_earthquake_does_not_claim_exact_prediction()
    print("risk calibration tests passed")
