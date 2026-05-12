#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "risk_engine.h"

/*
 * Academic prototype risk engine.
 *
 * Formal prototype structure, updated from the supplied research summary:
 *
 * H_d(x,t) = model-specific hazard proxy from normalized indicators
 * Risk_d(x,t) = A_d(x,t) * H_d(x,t) * E(x) * V_d(x)
 * P_d(x,t) is estimated later in Python by disaster-specific calibration
 * tables. The C layer intentionally does not output a probability.
 *
 * For this student prototype E(x)=1 and V_d(x)=1. Applicability A_d is
 * evaluated in Python because it depends on raw context such as snow depth,
 * slope angle, river proximity, and recent earthquake distance. If A_d=0,
 * Python returns "Not Applicable" without using this hazard score. Python sends
 * indicators normalized from 0 to 100; this engine converts them to 0 to 1
 * internally and returns a 0 to 100 score. These are simplified didactic
 * proxies for established model families, not operational forecasts.
 */

double clamp(double value, double min, double max) {
    if (value < min) {
        return min;
    }
    if (value > max) {
        return max;
    }
    return value;
}

const char *risk_level(double risk_score) {
    if (risk_score <= 25.0) {
        return "Low";
    }
    if (risk_score <= 50.0) {
        return "Medium";
    }
    if (risk_score <= 75.0) {
        return "High";
    }
    return "Critical";
}

double normalize_index(double value) {
    return clamp(value, 0.0, 100.0) / 100.0;
}

static double logistic_unit(double value, double steepness, double center) {
    return 1.0 / (1.0 + exp(-steepness * (value - center)));
}

static double saturating(double value) {
    if (value <= 0.0) {
        return 0.0;
    }
    return clamp(1.0 - exp(-value), 0.0, 1.0);
}

double flood_hazard(double rainfall, double discharge_anomaly, double soil_moisture, double low_elevation) {
    /*
     * SCS-CN inspired event-runoff proxy:
     * Pe = (P - 0.2S)^2 / (P + 0.8S), where CN controls S.
     * Here CN is approximated from soil saturation and low-elevation
     * susceptibility because the MVP does not have land-use/soil maps.
     */
    double rain = normalize_index(rainfall);
    double discharge = normalize_index(discharge_anomaly);
    double soil = normalize_index(soil_moisture);
    double low = normalize_index(low_elevation);
    double precipitation_mm = 5.0 + rain * 115.0;
    double curve_number = clamp(55.0 + soil * 32.0 + low * 10.0 + discharge * 3.0, 35.0, 98.0);
    double storage = (25400.0 / curve_number) - 254.0;
    double runoff_mm = 0.0;
    if (precipitation_mm > 0.2 * storage) {
        runoff_mm = pow(precipitation_mm - 0.2 * storage, 2.0) / (precipitation_mm + 0.8 * storage);
    }
    double runoff_ratio = clamp(runoff_mm / fmax(1.0, precipitation_mm), 0.0, 1.0);
    double hazard = clamp(0.45 * runoff_ratio + 0.25 * discharge + 0.20 * soil + 0.10 * low, 0.0, 1.0);
    if (rain < 0.18 && discharge < 0.20) {
        hazard = fmin(hazard, 0.24);
    }
    return hazard;
}

double earthquake_hazard(double magnitude_index, double shallow_depth, double distance_decay, double exposure) {
    /*
     * Gutenberg-Richter / Omori-ETAS inspired impact-rate proxy.
     * The normalized magnitude index is converted back to an Mw-like 3-8
     * range, then used as a productivity term. Distance decay and shallow
     * depth modulate impact. This is monitoring/impact risk, not deterministic
     * earthquake prediction.
     */
    double mag_unit = normalize_index(magnitude_index);
    double mag = 3.0 + mag_unit * 5.0;
    double shallow = normalize_index(shallow_depth);
    double distance_factor = normalize_index(distance_decay);
    double exposure_unit = normalize_index(exposure);
    double productivity = (pow(10.0, 0.45 * (mag - 3.0)) - 1.0) / (pow(10.0, 0.45 * 5.0) - 1.0);
    double conditional_rate = productivity * (0.25 + 0.75 * shallow) * fmax(0.03, distance_factor);
    return clamp(saturating(3.0 * conditional_rate) * (0.65 + 0.35 * exposure_unit), 0.0, 1.0);
}

double wildfire_hazard(double temperature, double wind, double dryness, double precipitation_deficit, double active_fire_proximity) {
    /*
     * Canadian Fire Weather Index style proxy:
     * ISI is approximated from wind and fine-fuel dryness, BUI from dryness and
     * precipitation deficit, and FWI from their interaction. Active fire
     * proximity is kept as ignition context when available.
     */
    double temp = normalize_index(temperature);
    double wind_unit = normalize_index(wind);
    double dry = normalize_index(dryness);
    double precip_def = normalize_index(precipitation_deficit);
    double active = normalize_index(active_fire_proximity);
    double isi = dry * (0.35 + 1.65 * wind_unit);
    double bui = 0.60 * dry + 0.40 * precip_def;
    double fwi_proxy = saturating(1.7 * isi * bui);
    double hazard = clamp(0.55 * fwi_proxy + 0.15 * temp + 0.20 * precip_def + 0.10 * active, 0.0, 1.0);
    if (dry < 0.25 && active < 0.20) {
        hazard = fmin(hazard, 0.24);
    }
    return hazard;
}

double drought_hazard(double precipitation_deficit, double soil_moisture_deficit, double temperature_anomaly, double dry_days) {
    /*
     * SPI/SPEI/PDSI inspired proxy. SPI is approximated by precipitation
     * deficit, SPEI by precipitation deficit plus temperature anomaly, and a
     * bucket-model stress term by soil moisture deficit.
     */
    double spi_like = normalize_index(precipitation_deficit);
    double soil_bucket_deficit = normalize_index(soil_moisture_deficit);
    double evap_demand = normalize_index(temperature_anomaly);
    double persistence = normalize_index(dry_days);
    double spei_like = clamp(0.65 * spi_like + 0.35 * evap_demand, 0.0, 1.0);
    double combined_deficit = sqrt(spi_like * soil_bucket_deficit);
    double hazard = clamp(0.35 * spi_like + 0.25 * spei_like + 0.25 * combined_deficit + 0.15 * persistence, 0.0, 1.0);
    if (persistence < 0.10 && spi_like < 0.60) {
        hazard = fmin(hazard, 0.24);
    }
    if (spi_like < 0.25 && persistence < 0.20) {
        hazard = fmin(hazard, 0.18);
    }
    return hazard;
}

double heatwave_hazard(double max_temperature_anomaly, double night_temperature_anomaly, double consecutive_hot_days, double apparent_temperature) {
    /*
     * Heat Index / Excess Heat Factor inspired proxy. Daytime anomaly,
     * nighttime anomaly, persistence, and apparent temperature interact because
     * heat-health risk grows when heat is intense and sustained.
     */
    double max_anom = normalize_index(max_temperature_anomaly);
    double night_anom = normalize_index(night_temperature_anomaly);
    double persistence = normalize_index(consecutive_hot_days);
    double apparent = normalize_index(apparent_temperature);
    double excess_heat_factor = clamp(max_anom * (0.45 + 0.35 * persistence + 0.20 * night_anom), 0.0, 1.0);
    double heat_index_proxy = clamp(0.60 * apparent + 0.25 * night_anom + 0.15 * max_anom, 0.0, 1.0);
    double hazard = clamp(0.55 * excess_heat_factor + 0.30 * heat_index_proxy + 0.15 * persistence, 0.0, 1.0);
    if (persistence < 0.25 && max_anom < 0.45) {
        hazard = fmin(hazard, 0.24);
    }
    return hazard;
}

double landslide_hazard(double rainfall_intensity, double antecedent_rainfall, double slope, double soil_moisture, double low_vegetation) {
    /*
     * Infinite-slope factor-of-safety and rainfall intensity-duration proxy.
     * The project lacks geotechnical parameters, so cohesion/friction are
     * represented by vegetation cover and soil wetness indicators.
     */
    double intensity = normalize_index(rainfall_intensity);
    double antecedent = normalize_index(antecedent_rainfall);
    double slope_unit = normalize_index(slope);
    double soil = normalize_index(soil_moisture);
    double low_veg = normalize_index(low_vegetation);
    double driving = 0.45 * slope_unit + 0.25 * soil + 0.20 * antecedent + 0.10 * intensity;
    double resistance = 0.30 + 0.30 * (1.0 - low_veg) + 0.25 * (1.0 - soil) + 0.15 * (1.0 - slope_unit);
    double infinite_slope_instability = logistic_unit(driving - resistance, 7.0, 0.0);
    double id_threshold_proxy = clamp(intensity * pow(0.15 + antecedent, 0.55), 0.0, 1.0);
    double hazard = clamp(0.62 * infinite_slope_instability + 0.38 * id_threshold_proxy, 0.0, 1.0);
    if (intensity < 0.20 && antecedent < 0.25) {
        hazard = fmin(hazard, 0.24);
    }
    return hazard;
}

double avalanche_hazard(double recent_snowfall, double snow_depth, double slope_criticality, double wind_transport, double temperature_change, double snowpack_instability) {
    /*
     * Snow-slab stability-index proxy:
     * SI = shear strength / gravitational + trigger load. Lower SI means
     * higher instability. Slope criticality and snowpack instability approximate
     * the weak-layer and propagation components discussed in avalanche models.
     */
    double snowfall = normalize_index(recent_snowfall);
    double snow = normalize_index(snow_depth);
    double slope = normalize_index(slope_criticality);
    double wind = normalize_index(wind_transport);
    double temp = normalize_index(temperature_change);
    double weak_layer = normalize_index(snowpack_instability);
    double load = 0.35 * snowfall + 0.25 * snow + 0.18 * wind + 0.12 * temp + 0.10 * weak_layer;
    double strength = 0.45 * (1.0 - weak_layer) + 0.25 * (1.0 - temp) + 0.20 * (1.0 - wind) + 0.10 * snow;
    double stability_index = strength / (load + 0.08);
    double stability_failure = clamp((1.55 - stability_index) / 1.55, 0.0, 1.0);
    double propagation_proxy = clamp(slope * (0.45 * snow + 0.35 * snowfall + 0.20 * wind), 0.0, 1.0);
    double hazard = clamp(0.65 * stability_failure + 0.35 * propagation_proxy, 0.0, 1.0);
    if (snowfall < 0.15 && snow < 0.15) {
        hazard = fmin(hazard, 0.20);
    }
    return hazard;
}

static void print_result(double hazard_unit) {
    const double exposure = 1.0;
    const double vulnerability = 1.0;
    double hazard_score = clamp(hazard_unit * exposure * vulnerability, 0.0, 1.0) * 100.0;

    printf(
        "{\"hazard_score\":%.2f,\"hazard_index\":%.4f,\"hazard_level\":\"%s\",\"risk_score\":%.2f,\"risk_level\":\"%s\"}\n",
        hazard_score,
        hazard_unit,
        risk_level(hazard_score),
        hazard_score,
        risk_level(hazard_score)
    );
}

static double arg_value(char *argv[], int index) {
    return atof(argv[index]);
}

int main(int argc, char *argv[]) {
    if (argc < 2) {
        fprintf(stderr, "Usage: risk_engine <disaster_type> <normalized indicators...>\n");
        return 1;
    }

    const char *type = argv[1];
    double hazard = 0.0;

    if (strcmp(type, "flood") == 0) {
        if (argc != 6) {
            fprintf(stderr, "Flood requires rainfall discharge_anomaly soil_moisture low_elevation.\n");
            return 1;
        }
        hazard = flood_hazard(arg_value(argv, 2), arg_value(argv, 3), arg_value(argv, 4), arg_value(argv, 5));
    } else if (strcmp(type, "earthquake") == 0) {
        if (argc != 6) {
            fprintf(stderr, "Earthquake requires magnitude_index shallow_depth distance_decay exposure.\n");
            return 1;
        }
        hazard = earthquake_hazard(arg_value(argv, 2), arg_value(argv, 3), arg_value(argv, 4), arg_value(argv, 5));
    } else if (strcmp(type, "wildfire") == 0) {
        if (argc != 7) {
            fprintf(stderr, "Wildfire requires temperature wind dryness precipitation_deficit active_fire_proximity.\n");
            return 1;
        }
        hazard = wildfire_hazard(arg_value(argv, 2), arg_value(argv, 3), arg_value(argv, 4), arg_value(argv, 5), arg_value(argv, 6));
    } else if (strcmp(type, "drought") == 0) {
        if (argc != 6) {
            fprintf(stderr, "Drought requires precipitation_deficit soil_moisture_deficit temperature_anomaly dry_days.\n");
            return 1;
        }
        hazard = drought_hazard(arg_value(argv, 2), arg_value(argv, 3), arg_value(argv, 4), arg_value(argv, 5));
    } else if (strcmp(type, "heatwave") == 0 || strcmp(type, "heat_wave") == 0) {
        if (argc != 6) {
            fprintf(stderr, "Heatwave requires max_temperature_anomaly night_temperature_anomaly consecutive_hot_days apparent_temperature.\n");
            return 1;
        }
        hazard = heatwave_hazard(arg_value(argv, 2), arg_value(argv, 3), arg_value(argv, 4), arg_value(argv, 5));
    } else if (strcmp(type, "landslide") == 0) {
        if (argc != 7) {
            fprintf(stderr, "Landslide requires rainfall_intensity antecedent_rainfall slope soil_moisture low_vegetation.\n");
            return 1;
        }
        hazard = landslide_hazard(arg_value(argv, 2), arg_value(argv, 3), arg_value(argv, 4), arg_value(argv, 5), arg_value(argv, 6));
    } else if (strcmp(type, "avalanche") == 0) {
        if (argc != 8) {
            fprintf(stderr, "Avalanche requires recent_snowfall snow_depth slope_criticality wind_transport temperature_change snowpack_instability.\n");
            return 1;
        }
        hazard = avalanche_hazard(arg_value(argv, 2), arg_value(argv, 3), arg_value(argv, 4), arg_value(argv, 5), arg_value(argv, 6), arg_value(argv, 7));
    } else {
        fprintf(stderr, "Unknown disaster type: %s\n", type);
        return 1;
    }

    print_result(hazard);
    return 0;
}
