# Digital System for Natural Disaster Risk Estimation Using Environmental Data

Academic full-stack prototype for monitoring environmental and geophysical indicators and estimating risk levels for floods, earthquakes, wildfires, droughts, heat waves, landslides, and avalanches.

This academic prototype estimates risk using public data and mathematical indicators. It is not an official emergency-warning system. It does not precisely predict disasters. Earthquakes are treated as monitoring and impact-risk estimation, not exact prediction.

## Technologies Used

- Frontend: React, Vite, Tailwind CSS, React-Leaflet, Recharts, Axios
- Backend: Python, FastAPI, Uvicorn, Requests
- Risk engine: C compiled with GCC and called from the FastAPI backend
- Map data: OpenStreetMap Overpass API for waterways, OpenTopoData for optional terrain/elevation sampling
- Data mode: public APIs with mock fallback data for offline student presentations

## General Use Command Cheat Sheet

Use these commands for normal local use. On this Windows setup, run the frontend and backend in two separate PowerShell windows.

One-time C engine compile:

```powershell
cd "$env:USERPROFILE\FolderLocation\disaster-risk-system\risk_engine"
gcc risk_engine.c -o risk_engine.exe -lm
```

If `-lm` fails:

```powershell
gcc risk_engine.c -o risk_engine.exe
```

Test the C engine directly:

```powershell
cd "$env:USERPROFILE\Desktop\disaster-risk-system\risk_engine"
.\risk_engine.exe flood 70 60 55 40
```

Start the backend:

```powershell
cd "$env:USERPROFILE\Desktop\disaster-risk-system\backend"
.\.venv\bin\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

If packages are missing:

```powershell
cd "$env:USERPROFILE\Desktop\disaster-risk-system\backend"
.\.venv\bin\python.exe -m pip install -r requirements.txt
```

Check the backend health endpoint:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

Start the frontend:

```powershell
cd "$env:USERPROFILE\Desktop\disaster-risk-system\frontend"
$env:Path = "C:\Program Files\nodejs;$env:Path"
& "C:\Program Files\nodejs\npm.cmd" run dev
```

If packages are missing:

```powershell
cd "$env:USERPROFILE\Desktop\disaster-risk-system\frontend"
$env:Path = "C:\Program Files\nodejs;$env:Path"
& "C:\Program Files\nodejs\npm.cmd" install
```

Open the dashboard:

```text
http://localhost:5173
```

Build the frontend for checking:

```powershell
cd "$env:USERPROFILE\Desktop\disaster-risk-system\frontend"
$env:Path = "C:\Program Files\nodejs;$env:Path"
& "C:\Program Files\nodejs\npm.cmd" run build
```

Git commands from the GitHub repository copy:

```powershell
cd "$env:USERPROFILE\Desktop\IW"
git status
git add README.md
git commit -m "Update README run commands"
git push origin master
```

Git Bash equivalents:

```bash
cd ~/Desktop/disaster-risk-system/risk_engine
gcc risk_engine.c -o risk_engine.exe -lm

cd ~/Desktop/disaster-risk-system/backend
./.venv/bin/python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8000

cd ~/Desktop/disaster-risk-system/frontend
npm run dev
```

## Quick Windows PowerShell Commands

Run these from PowerShell. Keep the backend and frontend running in two separate PowerShell windows.

Compile the C risk engine:

```powershell
cd "$env:USERPROFILE\Desktop\disaster-risk-system\risk_engine"
gcc risk_engine.c -o risk_engine.exe -lm
.\risk_engine.exe flood 70 60 55 40
```

If `-lm` fails on your Windows GCC setup, use:

```powershell
cd "$env:USERPROFILE\Desktop\disaster-risk-system\risk_engine"
gcc risk_engine.c -o risk_engine.exe
.\risk_engine.exe flood 70 60 55 40
```

Start the backend:

```powershell
cd "$env:USERPROFILE\Desktop\disaster-risk-system\backend"
.\.venv\bin\python.exe -m pip install -r requirements.txt
.\.venv\bin\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

If `.venv\bin\python.exe` does not exist, create the environment first:

```powershell
cd "$env:USERPROFILE\Desktop\disaster-risk-system\backend"
C:\msys64\ucrt64\bin\python.exe -m venv .venv
.\.venv\bin\python.exe -m pip install -r requirements.txt
.\.venv\bin\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Start the frontend:

```powershell
cd "$env:USERPROFILE\Desktop\disaster-risk-system\frontend"
$env:Path = "C:\Program Files\nodejs;$env:Path"
& "C:\Program Files\nodejs\npm.cmd" install
& "C:\Program Files\nodejs\npm.cmd" run dev
```

Then open:

```text
http://localhost:5173
```

## Project Structure

```text
disaster-risk-system/
├── frontend/
├── backend/
│   ├── main.py
│   ├── requirements.txt
│   ├── services/
│   ├── routes/
│   └── data/sample_locations.json
├── risk_engine/
│   ├── risk_engine.c
│   ├── risk_engine.h
│   └── README.md
└── README.md
```

## Frontend Installation

```powershell
cd "$env:USERPROFILE\Desktop\disaster-risk-system\frontend"
npm install
npm run dev
```

The dashboard runs at:

```text
http://localhost:5173
```

If `node` or `npm` is not recognized, install Node.js LTS, reopen PowerShell, and make sure this path is available:

```powershell
$env:Path = "C:\Program Files\nodejs;$env:Path"
node -v
npm -v
```

## Backend Installation

```powershell
cd "$env:USERPROFILE\Desktop\disaster-risk-system\backend"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

If PowerShell blocks activation:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
```

If your Python distribution creates a Unix-style venv layout on Windows:

```powershell
.\.venv\bin\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

The API runs at:

```text
http://127.0.0.1:8000
```

## Main API Endpoints

```text
GET  /api/health
GET  /api/locations
GET  /api/disasters
GET  /api/earthquakes?strict_real=true
GET  /api/weather?lat=47.2038&lon=28.4684&strict_real=true
GET  /api/providers?lat=47.2038&lon=28.4684&strict_real=true
GET  /api/risk/overview?strict_real=true&fast=true&optional_providers=false
GET  /api/risk/all?lat=47.2038&lon=28.4684&strict_real=true
GET  /api/risk/grid?disaster=drought&lat=47.2038&lon=28.4684&south=45.45&west=26.62&north=48.49&east=30.14&resolution=7&strict_real=true
POST /api/risk/calculate
```

Map and terrain endpoints:

```text
GET /api/map/rivers?lat=47.2038&lon=28.4684&south=45.45&west=26.62&north=48.49&east=30.14&strict_real=true
GET /api/map/terrain?lat=47.2038&lon=28.4684&radius_km=2&strict_real=true
GET /api/map/earthquakes?lat=37.5&lon=138.25&radius_km=1500&strict_real=true
```

`/api/risk/grid` returns disaster-specific grid cells with:

- cell center and bounds
- chance percent for the defined event window
- severity score if the event happens
- overall risk score, risk level, and confidence
- raw hazard from the C engine
- applicability mask result
- reason text
- raw indicators
- normalized indicators
- indicator explanations

If a disaster is not applicable in a cell, the backend returns:

```json
{
  "risk_score": 0,
  "risk_level": "Not Applicable",
  "chance_percent": 0,
  "severity_score": 0,
  "overall_risk_score": 0,
  "confidence": "Low",
  "applicable": false
}
```

The frontend displays one selected disaster layer at a time. The sidebar icon menu switches between flood, earthquake, wildfire, drought, heat-wave, landslide, and avalanche risk surfaces. Earthquake layers are described as impact-risk visualization, not earthquake prediction.

The current dashboard uses country/region bounds instead of city-centered circles. In `All countries / regions` mode, it draws one continuous overview grid across the monitored map area. Each grid cell is assigned to the country/region whose bounds contain the cell center, then the country/region score is aggregated from those covering grid cells. This lets the whole map display at once without making per-cell API calls for every country. The all-map overview targets about 0.42-degree Web Mercator cells; selecting one country/region targets about 0.18-degree cells, with an automatic performance cap for very large countries. Grid cells are generated in Web Mercator space so they look more square on the Leaflet map at high latitudes. The frontend also applies lightweight approximate land masks for coastal countries so obvious sea/ocean cells are skipped.

Performance note: dashboard startup uses `GET /api/risk/overview`, which calculates all monitored country/region records in one backend request, reuses the USGS earthquake feed once, uses short-lived Open-Meteo/USGS caches, and skips slow optional providers unless explicitly requested. Failed Open-Meteo responses are not cached; the backend retries with a smaller core weather-variable request, then can use NASA POWER aggregate climate data as a lower-resolution public-data fallback. The map renders only grid cells inside the current Leaflet viewport and uses Leaflet canvas rendering for the gridded layer.

Index note: the displayed percentage is now `chance_percent`, a conservative calibrated event-chance estimate for a defined time window. It is not produced by simply dividing the risk index by 100. The backend keeps the C hazard model as an internal signal, then applies disaster-specific calibration tables, a separate severity score, and a confidence estimate.

The frontend sends `strict_real=true`, so public API failures are not silently replaced with mock hazard events. If OpenTopoData is unavailable, the terrain-dependent layers may use static country terrain metadata so the map remains inspectable; this is labeled separately from live API data. Mock utilities remain in the backend code only for optional offline classroom demonstrations.

## External Data Providers

The backend now supports a provider layer that improves weak indicators when data is available:

- Open-Meteo Forecast: temperature, precipitation, humidity, wind, wind gusts, apparent temperature, snowfall, snow depth, freezing level, vapor pressure deficit, evapotranspiration, and soil moisture layers.
- Open-Meteo Flood: river discharge plus mean, median, maximum, p25, and p75 discharge fields used to estimate discharge anomaly.
- OpenTopoData: elevation and slope sampling for landslide, flood low-elevation, and avalanche masks.
- NASA POWER: optional backup climate and soil-wetness context for precipitation, temperature, humidity, wind, and soil wetness.
- USGS ShakeMap: optional earthquake shaking-intensity context when a recent USGS event has a ShakeMap product.
- WorldPop: optional population-density exposure index. Attempted for detailed single-location requests; skipped by the fast dashboard overview.
- NASA FIRMS: optional active-fire proximity for wildfire risk when a free FIRMS map key is configured.
- Copernicus CLMS and NOAA NOHRSC: documented as heavier optional raster/snow providers; adapters are represented in provider status output but are not required for the MVP.

NASA POWER, WorldPop, and ShakeMap are attempted automatically for detailed single-location requests. The optimized dashboard overview skips these slow optional providers for speed. Optional environment variables before starting the backend:

```powershell
$env:NASA_POWER_ENABLED = "1"
$env:SHAKEMAP_ENABLED = "1"
$env:NASA_FIRMS_MAP_KEY = "your-free-firms-map-key"
$env:WORLDPOP_ENABLED = "1"
$env:WORLDPOP_API_KEY = "optional-worldpop-key"
```

Use `NASA_POWER_ENABLED=0`, `SHAKEMAP_ENABLED=0`, or `WORLDPOP_ENABLED=0` only if you want to force those optional public sources off. FIRMS still requires `NASA_FIRMS_MAP_KEY`; without the key, wildfire risk uses Open-Meteo fire-weather indicators but no live active-fire detections.

## Compile the C Risk Engine on Windows

```powershell
cd "$env:USERPROFILE\Desktop\disaster-risk-system\risk_engine"
gcc risk_engine.c -o risk_engine.exe -lm
```

If `-lm` causes problems on Windows:

```powershell
gcc risk_engine.c -o risk_engine.exe
```

Example:

```powershell
.\risk_engine.exe flood 70 60 55 40
```

The backend calls `risk_engine.exe` on Windows. If the executable is missing and GCC is available, the backend attempts to compile it automatically. If the executable still cannot run, the backend uses a Python fallback formula.

## How to Run the Full App

Open two PowerShell windows.

Backend terminal:

```powershell
cd "$env:USERPROFILE\Desktop\disaster-risk-system\backend"
.\.venv\bin\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Frontend terminal:

```powershell
cd "$env:USERPROFILE\Desktop\disaster-risk-system\frontend"
$env:Path = "C:\Program Files\nodejs;$env:Path"
& "C:\Program Files\nodejs\npm.cmd" run dev
```

Then open:

```text
http://localhost:5173
```

## API Sources Used

- Open-Meteo Forecast API: temperature, humidity, precipitation, apparent temperature, wind speed, wind gusts, snow depth, snowfall, freezing level, evapotranspiration, vapor pressure deficit, and soil moisture where available.
- Open-Meteo Flood API: river discharge and ensemble/statistical discharge fields used to estimate discharge anomaly.
- USGS Earthquake GeoJSON Feed: recent earthquake magnitude, depth, coordinates, place, and time.
- USGS ShakeMap: optional shaking-intensity context for recent earthquakes when a ShakeMap product exists.
- OpenStreetMap Overpass API: nearby `waterway=river`, `waterway=stream`, and `waterway=canal` geometries for map overlays.
- OpenTopoData API: optional elevation sampling used to estimate terrain slope for landslide and avalanche prototype layers.
- NASA POWER: optional climate and soil-wetness backup context.
- WorldPop: optional population-density exposure context.
- NASA FIRMS: optional live active-fire detections when a free map key is configured.
- Copernicus CLMS and NOAA NOHRSC: heavier optional future raster/snow integrations noted by provider status.

## Risk Interpretation Pipeline

The backend separates hazard, chance, severity, and final risk:

```text
API data
-> raw indicators
-> normalized indicators 0-100
-> C hazard model, raw_hazard 0-1
-> disaster-specific calibration table
-> chance_percent for a defined time window
-> severity_score if the event happens
-> overall_risk_score = chance * severity * exposure/vulnerability
-> risk_level + confidence + explanation
```

Prototype assumptions:

```text
A_d(x,t) = 0 or 1 depending on disaster applicability
E(x) and V_d(x) are represented by simple prototype exposure/vulnerability factors.
Calibration tables are conservative placeholders until a historical event database is added.
```

Python sends normalized indicators from 0 to 100. The C engine converts them to 0 to 1 internally and returns a raw hazard score.
Applicability masks are evaluated in Python before C risk scoring. For example, avalanche is calculated only when snow, mountain elevation, and relevant slope conditions exist.

Event windows:

- Flood: chance of flood-producing conditions within the next 7 days.
- Wildfire: chance of ignition or spread-favorable conditions within the next 3-7 days.
- Drought: chance of drought developing or persisting within the next 30 days.
- Heat wave: chance of heat wave conditions within the next 7 days.
- Landslide: chance of rainfall-triggered landslide conditions within the next 3 days.
- Avalanche: chance of avalanche conditions within the next 48 hours.
- Earthquake: recent-earthquake impact and aftershock-aware risk context only; exact short-term earthquake prediction is unavailable.

The formula layer was updated from the supplied research PDF into simplified student-prototype versions of established model families:

- Flood: SCS Curve Number-inspired runoff proxy, where effective runoff is estimated from precipitation and a curve-number approximation, then combined with river discharge, saturation, and low elevation.
- Earthquake: Gutenberg-Richter and Omori/ETAS-inspired recent-event impact proxy. The app estimates earthquake impact risk from recent USGS events; it does not predict earthquake occurrence.
- Wildfire: Canadian Fire Weather Index-style proxy using an Initial Spread Index from wind and fine-fuel dryness, a Buildup Index from dryness and precipitation deficit, and active-fire proximity when available.
- Drought: SPI/SPEI/PDSI-inspired drought-stress proxy using precipitation deficit, temperature-driven evaporation demand, soil moisture deficit, and dry-day persistence.
- Drought false-risk reduction: current and recent rainfall damp the precipitation-deficit and dry-day terms so rainy conditions suppress short-term drought occurrence risk, while still allowing longer-term drought stress to appear when 30-day deficits persist.
- Evidence gates: flood, wildfire, drought, heat-wave, landslide, and avalanche formulas cap scores when a necessary trigger is missing. For example, drought needs stronger precipitation deficit or persistent dry days before it can move out of Low.
- Heatwave: Heat Index and Excess Heat Factor-inspired proxy using daytime anomaly, warm nights, apparent temperature, and consecutive hot-day persistence.
- Landslide: Infinite-slope factor-of-safety proxy plus rainfall intensity-duration triggering.
- Avalanche: Snow-slab stability-index and propagation proxy using snow loading, critical slope angle, wind transport, temperature change, and weak-layer susceptibility.

Special mathematical indicators still used in the preprocessing layer:

```text
earthquake distance_decay = exp(-distance_km / 100)
avalanche slope_criticality = exp(-(slope_angle - 38)^2 / (2 * 10^2))
```

Risk levels:

```text
0-25    Low
26-50   Medium
51-75   High
76-100  Critical
```

Risk levels use `overall_risk_score`, not chance alone. A low-chance/high-severity event and a high-chance/low-severity event can therefore have different final risk levels.

## Mock Fallback

The app works even if public APIs fail. Mock/sample data covers:

- Moldova / Chisinau
- Romania / Bucharest
- Italy / Rome
- Japan / Tokyo
- USA / California
- Nepal / Kathmandu
- Austria / Innsbruck

## Limitations

- The formulas are educational and not regionally calibrated.
- Public APIs may be unavailable, delayed, spatially coarse, or rate limited.
- Optional providers that require keys or heavier raster workflows are disabled unless configured.
- Gridded layers are small prototype rectangles with simplified land masks, not official country-boundary rasters or full remote-sensing products.
- Applicability masks reduce impossible risks, but they are still simplified classroom rules.
- Earthquake output estimates possible impact risk from recent events; it does not forecast earthquakes.
- No alert should be used for emergency decisions. Always consult official civil protection, meteorological, geological, hydrological, or avalanche agencies.

## Future Improvements

- Calibrate formulas with historical events and regional hazard records.
- Replace provider fallbacks with calibrated local climatology and validated historical hazard records.
- Add ERA5, IMERG, SMAP, Copernicus drought products, LHASA landslide products, or avalanche.report data for research-grade extensions.
- Add local JSON caching for public API responses.
- Add full raster heatmap rendering and layer toggles.
- Add automated tests for normalizers and C/Python formula parity.
