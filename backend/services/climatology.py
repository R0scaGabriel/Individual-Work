from __future__ import annotations

import math
from typing import Iterable


def calculate_percentile(value: float, historical_values: Iterable[float]) -> float | None:
    values = _clean_values(historical_values)
    if not values:
        return None
    below_or_equal = sum(1 for item in values if item <= value)
    return round((below_or_equal / len(values)) * 100, 2)


def calculate_anomaly(value: float, historical_mean: float | None) -> float | None:
    if historical_mean is None:
        return None
    return round(value - historical_mean, 3)


def calculate_standardized_anomaly(value: float, mean: float | None, std: float | None) -> float | None:
    if mean is None or std is None or std == 0:
        return None
    return round((value - mean) / std, 3)


def estimate_exceedance_probability(value: float, historical_values: Iterable[float]) -> float | None:
    values = _clean_values(historical_values)
    if not values:
        return None
    exceedances = sum(1 for item in values if item >= value)
    # Weibull plotting-position smoothing so extreme values do not return 0.
    return round((exceedances + 1) / (len(values) + 2), 4)


def recent_persistence(values: Iterable[float], threshold: float, comparator: str = ">=") -> int:
    count = 0
    for value in reversed(_clean_values(values)):
        if comparator == ">=" and value >= threshold:
            count += 1
        elif comparator == "<=" and value <= threshold:
            count += 1
        else:
            break
    return count


def _clean_values(values: Iterable[float]) -> list[float]:
    cleaned = []
    for value in values:
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number):
            cleaned.append(number)
    return cleaned
