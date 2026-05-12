from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


DATA_DIR = Path(__file__).resolve().parents[1] / "data"
CALIBRATION_TABLE_PATH = DATA_DIR / "calibration_tables.json"


def calibrate_probability(
    disaster_type: str,
    raw_hazard: float,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Map a 0-1 internal hazard value into a conservative chance estimate.

    The calibration tables are expert-judgement placeholders for a student
    prototype. They should be replaced by regional historical calibration when
    event archives and verification data are available.
    """

    context = context or {}
    disaster_type = disaster_type.lower().strip()
    table = calibration_tables().get(disaster_type) or calibration_tables()["flood"]
    hazard = max(0.0, min(1.0, float(raw_hazard or 0)))
    probability = _lookup_probability(hazard, table["bins"])

    evidence_gate = context.get("evidence_gate") or {}
    if evidence_gate.get("triggered"):
        probability *= float(evidence_gate.get("chance_multiplier", 0.65))

    if context.get("applicable") is False:
        probability = 0.0

    return {
        "probability": round(max(0.0, min(0.95, probability)), 4),
        "chance_percent": round(max(0.0, min(0.95, probability)) * 100, 1),
        "time_window_days": table.get("horizon_days"),
        "event_definition": table.get("event_definition", "Prototype event chance estimate."),
        "calibration_method": "conservative_table_v1",
        "calibration_note": "Prototype calibration table; not validated against a historical event archive.",
    }


@lru_cache(maxsize=1)
def calibration_tables() -> dict[str, Any]:
    with CALIBRATION_TABLE_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _lookup_probability(raw_hazard: float, bins: list[dict[str, float]]) -> float:
    for item in bins:
        if raw_hazard >= float(item["min"]) and raw_hazard < float(item["max"]):
            return float(item["probability"])
    return float(bins[-1]["probability"]) if bins else 0.0
