#ifndef RISK_ENGINE_H
#define RISK_ENGINE_H

double clamp(double value, double min, double max);
const char *risk_level(double risk_score);
double probability_from_unit_risk(double risk_unit, double k, double theta);

double normalize_index(double value);
double flood_hazard(double rainfall, double discharge_anomaly, double soil_moisture, double low_elevation);
double earthquake_hazard(double magnitude_index, double shallow_depth, double distance_decay, double exposure);
double wildfire_hazard(double temperature, double wind, double dryness, double precipitation_deficit, double active_fire_proximity);
double drought_hazard(double precipitation_deficit, double soil_moisture_deficit, double temperature_anomaly, double dry_days);
double heatwave_hazard(double max_temperature_anomaly, double night_temperature_anomaly, double consecutive_hot_days, double apparent_temperature);
double landslide_hazard(double rainfall_intensity, double antecedent_rainfall, double slope, double soil_moisture, double low_vegetation);
double avalanche_hazard(double recent_snowfall, double snow_depth, double slope_criticality, double wind_transport, double temperature_change, double snowpack_instability);

#endif
