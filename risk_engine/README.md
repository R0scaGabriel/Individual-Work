# C Risk Engine

This module calculates normalized internal hazard scores for seven disaster types.
The formulas were updated from the supplied research summary PDF into simplified
didactic proxies for established model families.

It uses the formal academic structure:

```text
H_d(x,t) = model-specific hazard proxy from normalized indicators
Risk_d(x,t) = A_d(x,t) * H_d(x,t) * E(x) * V_d(x)
Calibration and final chance/severity/risk interpretation happen in Python.
```

For this prototype:

```text
A_d(x,t) = evaluated in Python as 0 or 1
E(x) = 1
V_d(x) = 1
The C output is an internal hazard model output, not the final displayed probability.
```

The C executable calculates the hazard score only after Python has checked disaster applicability. If `A_d=0`, the backend returns `Not Applicable` without using the C score. Python then calibrates this raw hazard into `chance_percent`, computes `severity_score`, and combines them into `overall_risk_score`.

Model families represented in simplified form:

- Flood: SCS Curve Number event-runoff proxy plus river discharge and saturation.
- Earthquake: Gutenberg-Richter / Omori-ETAS-inspired impact-rate proxy for recent events.
- Wildfire: Canadian Fire Weather Index-style ISI/BUI/FWI proxy.
- Drought: SPI/SPEI/PDSI-inspired precipitation, evaporation-demand, and soil-stress proxy.
- Heatwave: Heat Index and Excess Heat Factor-inspired anomaly and persistence proxy.
- Landslide: Infinite-slope factor-of-safety plus rainfall intensity-duration threshold proxy.
- Avalanche: Snow-slab stability-index and propagation proxy.

Several formulas include evidence gates that cap the score when a required
trigger is missing. For example, drought cannot move out of Low from moderate
soil deficit alone if there is no persistent dry period and the precipitation
deficit is not strong.

Compile on Windows:

```powershell
gcc risk_engine.c -o risk_engine.exe -lm
```

If `-lm` causes linker issues:

```powershell
gcc risk_engine.c -o risk_engine.exe
```

Example:

```powershell
.\risk_engine.exe flood 70 60 55 40
```

Output is JSON. `hazard_score` and `hazard_index` are internal model outputs.
The `risk_score` and `risk_level` fields are kept as legacy hazard aliases for
command-line compatibility; the backend uses `hazard_index` and performs the
final probability calibration in Python:

```json
{"hazard_score":61.00,"hazard_index":0.6100,"hazard_level":"High","risk_score":61.00,"risk_level":"High"}
```

Scientific note: formulas are educational weighted indices only. Operational systems require local calibration, uncertainty analysis, and validation with historical events and official observations.
