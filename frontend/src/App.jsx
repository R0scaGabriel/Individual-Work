import { useCallback, useEffect, useMemo, useState } from "react";
import L from "leaflet";
import { CircleMarker, GeoJSON, MapContainer, Marker, Popup, Rectangle, TileLayer, useMap } from "react-leaflet";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  Database,
  Droplets,
  Filter,
  Flame,
  Globe2,
  Layers3,
  LocateFixed,
  Mountain,
  RefreshCcw,
  ShieldAlert,
  Snowflake,
  Sun,
  Thermometer,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import {
  getDisasters,
  getEarthquakeMap,
  getLocations,
  getRiskOverview,
  getRiskForLocation,
  getRiversForLocation,
} from "./api";
import { isApproximateLandCell } from "./landMasks";

const RISK_LEVELS = ["All", "Low", "Medium", "High", "Critical"];
const ALERT_LEVELS = ["High", "Critical"];
const GRID_DISASTERS = ["flood", "earthquake", "wildfire", "drought", "heatwave", "landslide", "avalanche"];
const LEVEL_COLORS = {
  Low: "#2f9e44",
  Medium: "#f59f00",
  High: "#f76707",
  Critical: "#d6336c",
  "Not Applicable": "#94a3b8",
};
const DISASTER_LABELS = {
  flood: "Flood",
  earthquake: "Earthquake",
  wildfire: "Wildfire",
  drought: "Drought",
  heatwave: "Heat Wave",
  landslide: "Landslide",
  avalanche: "Avalanche",
};
const DISASTER_ICONS = {
  flood: Droplets,
  earthquake: Activity,
  wildfire: Flame,
  drought: Sun,
  heatwave: Thermometer,
  landslide: Mountain,
  avalanche: Snowflake,
};
const DISASTER_ACCENTS = {
  flood: "#228be6",
  earthquake: "#7048e8",
  wildfire: "#f76707",
  drought: "#c88719",
  heatwave: "#d6336c",
  landslide: "#795548",
  avalanche: "#0c8599",
};
const GRID_RENDERER = L.canvas({ padding: 0.35 });
const MAX_RENDERED_GRID_CELLS = 6500;

function createMarkerIcon(level) {
  const color = LEVEL_COLORS[level] || "#64748b";
  return L.divIcon({
    className: "",
    html: `<div class="risk-marker" style="background:${color}">${level?.slice(0, 1) || "R"}</div>`,
    iconSize: [30, 30],
    iconAnchor: [15, 15],
    popupAnchor: [0, -15],
  });
}

function FitBounds({ markers, activeLocation }) {
  const map = useMap();

  useEffect(() => {
    if (activeLocation) {
      if (activeLocation.bounds) {
        map.fitBounds(activeLocation.bounds, { padding: [28, 28], maxZoom: 7 });
        return;
      }
      map.setView([activeLocation.lat, activeLocation.lon], 7);
      return;
    }
    if (!markers.length) {
      return;
    }
    const bounds = L.latLngBounds(markers.map((item) => [item.lat, item.lon]));
    map.fitBounds(bounds, { padding: [36, 36], maxZoom: 5 });
  }, [map, markers, activeLocation]);

  return null;
}

function MapViewportTracker({ onChange }) {
  const map = useMap();

  useEffect(() => {
    function syncViewport() {
      const bounds = map.getBounds();
      onChange({
        south: Number(bounds.getSouth().toFixed(4)),
        west: Number(bounds.getWest().toFixed(4)),
        north: Number(bounds.getNorth().toFixed(4)),
        east: Number(bounds.getEast().toFixed(4)),
        zoom: map.getZoom(),
      });
    }

    syncViewport();
    map.on("moveend zoomend resize", syncViewport);
    return () => {
      map.off("moveend zoomend resize", syncViewport);
    };
  }, [map, onChange]);

  return null;
}

async function loadRiskBundlesInBatches(locationData, disasterData, batchSize = 4) {
  const bundles = [];
  for (let index = 0; index < locationData.length; index += batchSize) {
    const batch = locationData.slice(index, index + batchSize);
    const batchResults = await Promise.all(
      batch.map((location) =>
        getRiskForLocation(location).catch(() => createUnavailableBundle(location, disasterData)),
      ),
    );
    bundles.push(...batchResults);
  }
  return bundles;
}

function createUnavailableBundle(location, disasterData) {
  return {
    location,
    weather: { source: "unavailable", current: {}, daily: [] },
    flood: { source: "unavailable" },
    terrain: { source: "unavailable" },
    providers: {
      open_meteo: {
        source: "open-meteo",
        status: "unavailable",
        reason: "Weather, flood, and terrain requests were unavailable for this refresh.",
      },
    },
    nearest_earthquake: null,
    results: disasterData.map((disaster) => ({
      disaster_type: disaster.id,
      label: disaster.label,
      risk_score: 0,
      chance_percent: 0,
      severity_score: 0,
      overall_risk_score: 0,
      confidence: "Low",
      raw_hazard: 0,
      probability: 0,
      risk_level: "Not Applicable",
      indicators: {},
      indicator_details: [],
      model_family: "Unavailable while public API request is offline.",
      calculation_engine: "request_unavailable",
      explanation: "The public API request failed for this country/region, so no score is shown.",
      recommendation: "Refresh when the API connection is available.",
      location,
      lat: location.lat,
      lon: location.lon,
    })),
  };
}

function App() {
  const [locations, setLocations] = useState([]);
  const [disasters, setDisasters] = useState([]);
  const [riskBundles, setRiskBundles] = useState([]);
  const [selectedDisaster, setSelectedDisaster] = useState("flood");
  const [selectedRiskLevel, setSelectedRiskLevel] = useState("All");
  const [selectedLocation, setSelectedLocation] = useState("All");
  const [selectedRisk, setSelectedRisk] = useState(null);
  const [selectedGridCell, setSelectedGridCell] = useState(null);
  const [rivers, setRivers] = useState(null);
  const [riskGrid, setRiskGrid] = useState([]);
  const [earthquakeMap, setEarthquakeMap] = useState({ events: [], heatmap_points: [] });
  const [mapViewport, setMapViewport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [mapLoading, setMapLoading] = useState(false);
  const [error, setError] = useState("");

  async function loadDashboard() {
    setLoading(true);
    setError("");
    try {
      const [locationData, disasterData, overviewBundles] = await Promise.all([
        getLocations(),
        getDisasters(),
        getRiskOverview().catch(() => null),
      ]);
      setLocations(locationData);
      setDisasters(disasterData);
      const bundles = overviewBundles?.length
        ? overviewBundles
        : await loadRiskBundlesInBatches(locationData, disasterData, 8);
      setRiskBundles(bundles);
      const records = bundles.flatMap((bundle) => bundle.results);
      setSelectedRisk(records.find((record) => record.disaster_type === selectedDisaster) || records[0] || null);
    } catch (requestError) {
      setError("Backend is not reachable. Start FastAPI on http://localhost:8000 and reload the dashboard.");
      console.error(requestError);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadDashboard();
  }, []);

  const allRiskItems = useMemo(
    () =>
      riskBundles.flatMap((bundle) =>
        bundle.results.map((result) => ({
          ...result,
          locationName: bundle.location.name,
          country: bundle.location.country,
          region: bundle.location.region,
          weatherSource: bundle.weather?.source,
          providers: bundle.providers || {},
        })),
      ),
    [riskBundles],
  );

  const activeMapLocation = useMemo(() => {
    if (selectedLocation !== "All") {
      return locations.find((location) => location.id === selectedLocation) || null;
    }
    return selectedRisk?.location || locations[0] || null;
  }, [locations, selectedLocation, selectedRisk]);

  const activeGridDisaster = selectedDisaster;

  useEffect(() => {
    if (!allRiskItems.length) {
      return;
    }

    const scopedRecords = allRiskItems.filter((item) => {
      const disasterMatch = item.disaster_type === selectedDisaster;
      const locationMatch = selectedLocation === "All" || item.location.id === selectedLocation;
      return disasterMatch && locationMatch;
    });
    const nextRisk = scopedRecords[0] || allRiskItems.find((item) => item.disaster_type === selectedDisaster) || allRiskItems[0];
    const currentStillValid =
      selectedRisk?.disaster_type === selectedDisaster &&
      (selectedLocation === "All" || selectedRisk?.location?.id === selectedLocation);

    if (!currentStillValid && nextRisk) {
      setSelectedRisk(nextRisk);
      setSelectedGridCell(null);
    }
  }, [allRiskItems, selectedDisaster, selectedLocation, selectedRisk?.disaster_type, selectedRisk?.location?.id]);

  useEffect(() => {
    if (!activeMapLocation) {
      return;
    }
    if (selectedLocation === "All") {
      setRivers(null);
      setEarthquakeMap({ events: [], heatmap_points: [] });
      setRiskGrid([]);
      setMapLoading(false);
      return;
    }

    let cancelled = false;
    async function loadMapLayers() {
      setMapLoading(true);
      try {
        const wantsFlood = activeGridDisaster === "flood";
        const wantsEarthquake = activeGridDisaster === "earthquake";
        const [riverData, earthquakeData] = await Promise.all([
          wantsFlood ? getRiversForLocation(activeMapLocation, 22) : Promise.resolve(null),
          wantsEarthquake ? getEarthquakeMap(activeMapLocation, 1500) : Promise.resolve({ events: [], heatmap_points: [] }),
        ]);
        if (!cancelled) {
          setRivers(riverData);
          setEarthquakeMap(earthquakeData);
          setRiskGrid([]);
          setSelectedGridCell(null);
        }
      } catch (mapError) {
        console.error(mapError);
        if (!cancelled) {
          setRivers(null);
          setEarthquakeMap({ events: [], heatmap_points: [] });
          setRiskGrid([]);
          setSelectedGridCell(null);
        }
      } finally {
        if (!cancelled) {
          setMapLoading(false);
        }
      }
    }

    loadMapLayers();
    return () => {
      cancelled = true;
    };
  }, [activeMapLocation, selectedDisaster, activeGridDisaster, selectedLocation]);

  const filteredRisks = useMemo(() => {
    return allRiskItems.filter((item) => {
      const disasterMatch = item.disaster_type === selectedDisaster;
      const levelMatch = selectedRiskLevel === "All" || item.risk_level === selectedRiskLevel;
      const locationMatch = selectedLocation === "All" || item.location.id === selectedLocation;
      return disasterMatch && levelMatch && locationMatch;
    });
  }, [allRiskItems, selectedDisaster, selectedRiskLevel, selectedLocation]);

  const overviewGrid = useMemo(() => {
    return buildOverviewGrid(filteredRisks, selectedLocation === "All" ? 0.42 : 0.18);
  }, [filteredRisks, selectedLocation]);

  const displayedGrid = overviewGrid.length ? overviewGrid : riskGrid;
  const renderedGrid = useMemo(() => filterRenderableGrid(displayedGrid, mapViewport), [displayedGrid, mapViewport]);
  const countryGridScores = useMemo(() => aggregateCountryGridScores(displayedGrid), [displayedGrid]);

  const scoredRisks = useMemo(() => {
    return filteredRisks.map((item) => {
      const aggregate = countryGridScores.get(item.location.id);
      if (!aggregate) {
        return item;
      }
      return {
        ...item,
        risk_score: aggregate.average,
        overall_risk_score: aggregate.average,
        chance_percent: aggregate.chancePercent,
        severity_score: aggregate.severityScore,
        confidence: aggregate.confidence,
        risk_level: aggregate.level,
        probability: aggregate.chancePercent / 100,
        explanation: `${item.label} country score is aggregated from ${aggregate.count} visible grid cells. Average score: ${aggregate.average.toFixed(1)}; maximum cell score: ${aggregate.max.toFixed(1)}.`,
        grid_cell_count: aggregate.count,
        max_grid_score: aggregate.max,
      };
    });
  }, [countryGridScores, filteredRisks]);

  const mapMarkers = useMemo(() => {
    const grouped = new Map();
    for (const item of scoredRisks) {
      const current = grouped.get(item.location.id);
      if (!current || item.risk_score > current.risk_score) {
        grouped.set(item.location.id, item);
      }
    }
    return [...grouped.values()];
  }, [scoredRisks]);

  const highestSelectedRisk = useMemo(
    () => scoredRisks.reduce((highest, item) => (!highest || item.risk_score > highest.risk_score ? item : highest), null),
    [scoredRisks],
  );

  const visibleAlerts = useMemo(() => {
    return scoredRisks.filter((item) => {
      const alertLevel = ALERT_LEVELS.includes(item.risk_level);
      const disasterMatch = item.disaster_type === selectedDisaster;
      const levelMatch = selectedRiskLevel === "All" || item.risk_level === selectedRiskLevel;
      const locationMatch = selectedLocation === "All" || item.location.id === selectedLocation;
      return alertLevel && disasterMatch && levelMatch && locationMatch;
    });
  }, [scoredRisks, selectedDisaster, selectedRiskLevel, selectedLocation]);

  const distributionData = useMemo(() => {
    const byDisaster = new Map();
    const records = [
      ...scoredRisks,
      ...displayedGrid.filter((cell) => cell.applicable && cell.risk_level !== "Not Applicable"),
    ];
    for (const item of records) {
      if (!["Low", "Medium", "High", "Critical"].includes(item.risk_level)) {
        continue;
      }
      const key = item.disaster_type;
      const row = byDisaster.get(key) || {
        type: DISASTER_LABELS[key],
        disaster_type: key,
        Low: 0,
        Medium: 0,
        High: 0,
        Critical: 0,
      };
      row[item.risk_level] += 1;
      byDisaster.set(key, row);
    }
    return [...byDisaster.values()];
  }, [displayedGrid, scoredRisks, selectedDisaster]);

  const comparisonData = useMemo(() => {
    return scoredRisks.map((match) => {
      return {
        location: match.locationName,
        risk: Number((match?.risk_score || 0).toFixed(1)),
        level: match?.risk_level || "Low",
      };
    });
  }, [scoredRisks]);

  const selectedMapRecord = selectedGridCell || selectedRisk;
  const selectedBundle = riskBundles.find((bundle) => bundle.location.id === selectedRisk?.location?.id);
  const selectedWeather = selectedBundle?.weather?.current || {};
  const selectedDaily = selectedBundle?.weather?.daily || [];
  const selectedDataRows = selectedMapRecord?.indicator_details || [];
  const selectedApplicability = selectedGridCell?.applicability || selectedRisk?.applicability || null;
  const selectedProviders = selectedGridCell?.providers || selectedBundle?.providers || selectedRisk?.providers || {};
  const activeFloodRisk = allRiskItems.find((item) => item.location.id === activeMapLocation?.id && item.disaster_type === "flood");
  const riverColor = LEVEL_COLORS[activeFloodRisk?.risk_level] || "#228be6";
  const ActiveDisasterIcon = DISASTER_ICONS[selectedDisaster] || Layers3;
  const activeDisasterLabel = DISASTER_LABELS[selectedDisaster] || "Disaster";
  const activeLayerDescription =
    selectedDisaster === "earthquake"
      ? "Continuous impact-risk grid from recent USGS data. This is not earthquake prediction."
      : "One continuous grid from live country/region API records; country scores are aggregated from covering cells.";

  function handleGridCellClick(cell) {
    setSelectedGridCell(cell);
    const matchingRisk = allRiskItems.find(
      (item) => item.location.id === cell.location?.id && item.disaster_type === cell.disaster_type,
    );
    if (matchingRisk) {
      setSelectedRisk(matchingRisk);
    }
  }

  const handleMapViewportChange = useCallback((nextViewport) => {
    setMapViewport((previous) => {
      if (
        previous &&
        previous.south === nextViewport.south &&
        previous.west === nextViewport.west &&
        previous.north === nextViewport.north &&
        previous.east === nextViewport.east &&
        previous.zoom === nextViewport.zoom
      ) {
        return previous;
      }
      return nextViewport;
    });
  }, []);

  return (
    <div className="min-h-screen bg-[#eef3f8] text-ink">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-[1500px] flex-col gap-4 px-4 py-5 md:flex-row md:items-center md:justify-between lg:px-6">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded bg-[#1967d2] text-white">
              <Globe2 size={24} aria-hidden="true" />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-normal md:text-2xl">
                Digital System for Natural Disaster Risk Estimation
              </h1>
              <p className="text-sm text-muted">
                Academic prototype using public environmental data, geophysical feeds, and mathematical indicators
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={loadDashboard}
            className="inline-flex h-10 items-center justify-center gap-2 rounded border border-slate-300 bg-white px-4 text-sm font-semibold text-slate-700 hover:bg-slate-50"
            title="Refresh dashboard data"
          >
            <RefreshCcw size={16} aria-hidden="true" />
            Refresh
          </button>
        </div>
      </header>

      <main className="mx-auto grid max-w-[1500px] gap-5 px-4 py-5 lg:grid-cols-[300px_minmax(0,1fr)] lg:px-6">
        <aside className="space-y-5">
          <section className="rounded border border-slate-200 bg-panel p-4 shadow-soft">
            <div className="mb-4 flex items-center gap-2">
              <Filter size={18} className="text-[#1967d2]" aria-hidden="true" />
              <h2 className="text-base font-bold">Filters</h2>
            </div>
            <div className="space-y-4">
              <DisasterIconMenu
                disasters={disasters}
                selected={selectedDisaster}
                onSelect={(disasterId) => {
                  setSelectedDisaster(disasterId);
                  setSelectedGridCell(null);
                }}
              />

              <SelectField label="Risk level" value={selectedRiskLevel} onChange={setSelectedRiskLevel}>
                {RISK_LEVELS.map((level) => (
                  <option key={level} value={level}>
                    {level}
                  </option>
                ))}
              </SelectField>

              <SelectField
                label="Country / region"
                value={selectedLocation}
                onChange={(value) => {
                  setSelectedLocation(value);
                  setSelectedGridCell(null);
                }}
              >
                <option value="All">All countries / regions</option>
                {locations.map((location) => (
                  <option key={location.id} value={location.id}>
                    {location.name}
                  </option>
                ))}
              </SelectField>
            </div>
          </section>

          <section className="rounded border border-slate-200 bg-panel p-4 shadow-soft">
            <div className="mb-3 flex items-center gap-2">
              <ShieldAlert size={18} className="text-[#d6336c]" aria-hidden="true" />
              <h2 className="text-base font-bold">Alerts</h2>
            </div>
            <div className="max-h-[460px] space-y-3 overflow-auto pr-1">
              {visibleAlerts.length === 0 && <p className="text-sm text-muted">No alerts match the selected filters.</p>}
              {visibleAlerts.slice(0, 12).map((alert) => (
                <button
                  key={`${alert.location.id}-${alert.disaster_type}`}
                  type="button"
                  onClick={() => { setSelectedRisk(alert); setSelectedGridCell(null); }}
                  className="w-full rounded border border-slate-200 bg-slate-50 p-3 text-left hover:border-slate-300"
                >
                  <div className="mb-2 flex items-center justify-between gap-3">
                    <span className="text-sm font-bold">{alert.label}</span>
                    <RiskBadge level={alert.risk_level} />
                  </div>
                  <p className="text-xs font-semibold text-slate-600">
                    {alert.locationName}, {alert.country} - {alert.risk_score.toFixed(1)}
                  </p>
                  <p className="mt-2 text-xs leading-5 text-slate-600">{alert.recommendation}</p>
                </button>
              ))}
            </div>
          </section>
        </aside>

        <section className="space-y-5">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <SummaryCard icon={<LocateFixed size={20} />} label="Monitored countries/regions" value={locations.length} detail="Country-scale area set" />
            <SummaryCard icon={<AlertTriangle size={20} />} label="Visible alerts" value={visibleAlerts.length} detail="Filtered High or Critical records" />
            <SummaryCard
              icon={<AlertTriangle size={20} />}
              label="Highest selected risk"
              value={highestSelectedRisk ? highestSelectedRisk.risk_level : "N/A"}
              detail={highestSelectedRisk ? `${highestSelectedRisk.label} - ${highestSelectedRisk.locationName}` : "Waiting for data"}
            />
            <SummaryCard
              icon={<Layers3 size={20} />}
              label="Active map layer"
              value={activeDisasterLabel}
              detail={`${filteredRisks.length} monitored records`}
            />
          </div>

          {error && <div className="rounded border border-red-200 bg-red-50 p-4 text-sm font-medium text-red-700">{error}</div>}

          <section className="rounded border border-blue-200 bg-blue-50 p-4 text-sm leading-6 text-blue-950">
            This academic prototype estimates risk using public data and mathematical indicators. It is not an official emergency-warning system.
          </section>

          <div className="grid gap-5 xl:grid-cols-[minmax(0,1.3fr)_minmax(380px,0.7fr)]">
            <section className="h-[560px] overflow-hidden rounded border border-slate-200 bg-panel shadow-soft">
              <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
                <div className="flex min-w-0 items-center gap-2">
                  <ActiveDisasterIcon
                    size={18}
                    className="shrink-0"
                    style={{ color: DISASTER_ACCENTS[selectedDisaster] || "#1967d2" }}
                    aria-hidden="true"
                  />
                  <div className="min-w-0">
                    <h2 className="truncate text-base font-bold">{activeDisasterLabel} Risk Surface</h2>
                    <p className="truncate text-xs text-slate-500">{activeLayerDescription}</p>
                  </div>
                </div>
                <span className="text-xs font-semibold text-slate-500">
                  {mapLoading ? "Loading layers" : `${renderedGrid.length}/${displayedGrid.length} rendered grid cells`}
                </span>
              </div>
              <div className="relative h-[512px]">
                <MapContainer center={[45, 20]} zoom={3} scrollWheelZoom preferCanvas>
                  <TileLayer
                    attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                  />
                  <FitBounds markers={mapMarkers} activeLocation={selectedLocation === "All" ? null : activeMapLocation} />
                  <MapViewportTracker onChange={handleMapViewportChange} />

                  {rivers?.features?.length > 0 && (
                    <GeoJSON
                      key={`${activeMapLocation?.id}-rivers-${riverColor}`}
                      data={rivers}
                      style={() => ({ color: riverColor, weight: 4, opacity: 0.72 })}
                      onEachFeature={(feature, layer) => {
                        layer.bindPopup(`${feature.properties?.name || "Waterway"} (${feature.properties?.waterway || "river"})`);
                      }}
                    />
                  )}

                  {renderedGrid.map((cell) => (
                    <Rectangle
                      key={cell.id}
                      bounds={cell.bounds}
                      renderer={GRID_RENDERER}
                      pathOptions={gridCellStyle(cell)}
                      eventHandlers={{
                        click: () => handleGridCellClick(cell),
                      }}
                    >
                      <Popup>
                        <GridCellPopup cell={cell} />
                      </Popup>
                    </Rectangle>
                  ))}

                  {selectedDisaster === "earthquake" &&
                    earthquakeMap.events?.map((event) => (
                      <CircleMarker
                        key={event.id}
                        center={[event.lat, event.lon]}
                        radius={event.display_radius}
                        pathOptions={{
                          color: "#7048e8",
                          fillColor: "#7048e8",
                          fillOpacity: 0.22 + event.intensity * 0.38,
                          opacity: 0.75,
                        }}
                      >
                        <Popup>
                          <div className="space-y-2">
                            <p className="text-sm font-bold">{event.place}</p>
                            <p className="text-xs text-slate-600">Magnitude {event.magnitude} - depth {event.depth} km</p>
                            <p className="text-xs text-slate-600">Distance to selected location: {event.distance_km} km</p>
                          </div>
                        </Popup>
                      </CircleMarker>
                    ))}

                  {mapMarkers.map((item) => (
                    <Marker
                      key={`${item.location.id}-${item.disaster_type}`}
                      position={[item.lat, item.lon]}
                      icon={createMarkerIcon(item.risk_level)}
                      eventHandlers={{ click: () => { setSelectedRisk(item); setSelectedGridCell(null); } }}
                    >
                      <Popup>
                        <div className="space-y-2">
                          <p className="text-sm font-bold">{item.locationName}</p>
                          <p className="text-xs text-slate-500">
                            {item.label} - {item.region}
                          </p>
                          <div className="flex items-center justify-between gap-3">
                            <span className="text-xs font-semibold text-slate-500">Risk score</span>
                            <span className="text-sm font-bold">{item.risk_score.toFixed(1)}</span>
                          </div>
                          <RiskBadge level={item.risk_level} />
                          <p className="text-xs leading-5 text-slate-600">{item.explanation}</p>
                        </div>
                      </Popup>
                    </Marker>
                  ))}
                </MapContainer>
                <RiskLegend />
                {!mapLoading && selectedLocation !== "All" && riskGrid.length > 0 && riskGrid.every((cell) => !cell.applicable) && (
                  <div className="absolute bottom-3 left-3 z-[500] max-w-[300px] rounded border border-slate-200 bg-white/95 px-3 py-2 text-xs font-semibold text-slate-600 shadow-soft">
                    Detailed cells are muted because this hazard is not physically applicable in most of the selected area.
                  </div>
                )}
              </div>
            </section>

            <section className="rounded border border-slate-200 bg-panel p-4 shadow-soft">
              <div className="mb-3 flex items-center gap-2">
                <Database size={18} className="text-[#1967d2]" aria-hidden="true" />
                <h2 className="text-base font-bold">Data Panel</h2>
              </div>
              {selectedMapRecord ? (
                <div className="space-y-4">
                  <div className="flex flex-wrap items-center justify-between gap-3 rounded bg-slate-50 p-3">
                    <div>
                      <p className="text-sm font-bold">
                        {selectedGridCell
                          ? `${DISASTER_LABELS[selectedGridCell.disaster_type]} ${selectedGridCell.overview ? "overview" : "grid"} cell`
                          : `${selectedRisk.label} - ${selectedRisk.locationName}`}
                      </p>
                      <p className="text-xs text-slate-500">
                        {selectedGridCell
                          ? `${selectedGridCell.locationName || "Cell"} center: ${selectedGridCell.lat}, ${selectedGridCell.lon}`
                          : `Calculation engine: ${selectedRisk.calculation_engine}`}
                      </p>
                    </div>
                    <RiskBadge level={selectedMapRecord.risk_level} />
                  </div>
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <Metric label="Chance" value={`${formatValue(selectedMapRecord.chance_percent ?? (selectedMapRecord.probability ?? 0) * 100)}%`} />
                    <Metric label="Severity if it happens" value={`${formatValue(selectedMapRecord.severity_score)} / 100`} />
                    <Metric label="Overall risk score" value={Number(selectedMapRecord.overall_risk_score ?? selectedMapRecord.risk_score).toFixed(1)} />
                    <Metric label="Confidence" value={selectedMapRecord.confidence || "N/A"} />
                    <Metric label="Raw hazard" value={`${formatValue((selectedMapRecord.raw_hazard ?? selectedMapRecord.hazard_index ?? 0) * 100)} / 100`} />
                    {selectedMapRecord.time_window_days && <Metric label="Time window" value={`${selectedMapRecord.time_window_days} days`} />}
                    <Metric label="Model family" value={selectedMapRecord.model_family || "Academic risk proxy"} />
                    {selectedGridCell && <Metric label="Cell mode" value={selectedGridCell.overview ? "Fast overview" : selectedGridCell.applicable ? "Detailed applicable" : "Muted / not applicable"} />}
                    <Metric label="Temperature" value={`${selectedWeather.temperature_2m ?? "N/A"} C`} />
                    <Metric label="Precipitation" value={`${selectedWeather.precipitation ?? "N/A"} mm`} />
                    <Metric label="Humidity" value={`${selectedWeather.relative_humidity_2m ?? "N/A"}%`} />
                    <Metric label="Wind speed" value={`${selectedWeather.wind_speed_10m ?? "N/A"} km/h`} />
                  </div>
                  <ProviderStatusPanel providers={selectedProviders} />
                  {selectedGridCell && (
                    <section className="rounded border border-slate-200 bg-white p-3">
                      <h3 className="mb-2 text-sm font-bold">Applicability conditions</h3>
                      <p className="mb-2 text-sm leading-6 text-slate-600">{selectedGridCell.reason}</p>
                      <div className="space-y-2">
                        {selectedApplicability?.conditions?.map((condition) => (
                          <div key={condition.label} className="flex items-start justify-between gap-3 text-sm">
                            <span className="text-slate-600">{condition.label}</span>
                            <span className={condition.passed ? "font-semibold text-green-700" : "font-semibold text-slate-500"}>
                              {condition.value ? `${condition.value} - ` : ""}
                              {condition.passed ? "passed" : "not met"}
                            </span>
                          </div>
                        ))}
                      </div>
                    </section>
                  )}
                  <div>
                    <h3 className="mb-2 text-sm font-bold">Indicators used in this calculation</h3>
                    <div className="overflow-auto rounded border border-slate-200">
                      <table className="w-full min-w-[520px] text-left text-sm">
                        <thead className="bg-slate-50 text-xs uppercase text-slate-500">
                          <tr>
                            <th className="px-3 py-2">Indicator</th>
                            <th className="px-3 py-2">Value</th>
                            <th className="px-3 py-2">Index 0-100</th>
                            <th className="px-3 py-2">Why it matters</th>
                          </tr>
                        </thead>
                        <tbody>
                          {selectedDataRows.map((row) => (
                            <tr key={row.key} className="border-t border-slate-100 align-top">
                              <td className="px-3 py-2 font-semibold">{row.label}</td>
                              <td className="px-3 py-2">
                                {formatValue(row.value)} {row.unit}
                              </td>
                              <td className="px-3 py-2 font-bold">{Number(row.normalized_value).toFixed(1)}</td>
                              <td className="px-3 py-2 text-slate-600">{row.explanation}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                  <p className="text-sm leading-6 text-slate-600">
                    {selectedGridCell ? selectedGridCell.reason : selectedRisk.explanation}
                  </p>
                  <p className="rounded border border-amber-200 bg-amber-50 p-3 text-sm leading-6 text-amber-900">
                    {selectedGridCell
                      ? selectedGridCell.overview
                        ? "This overview grid reuses country/region API records for fast whole-map visualization. Select one country/region for detailed cell sampling."
                        : "This grid layer is an academic visualization. Verify with official agencies before any real decision."
                      : selectedRisk.recommendation}
                  </p>
                  <MiniWeatherTable rows={selectedDaily.slice(-5)} />
                </div>
              ) : (
                <p className="text-sm text-muted">Select a marker or alert to inspect indicators.</p>
              )}
            </section>
          </div>

          <div className="grid gap-5 xl:grid-cols-2">
            <section className="rounded border border-slate-200 bg-panel p-4 shadow-soft">
              <div className="mb-2 flex items-center gap-2">
                <BarChart3 size={18} className="text-[#1967d2]" aria-hidden="true" />
                <h2 className="text-base font-bold">Risk Distribution by Disaster Type</h2>
              </div>
              <p className="mb-4 text-sm leading-6 text-slate-600">
                This chart groups calculated grid cells or monitored records by disaster type and risk level.
              </p>
              <div className="h-[320px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={distributionData} margin={{ top: 10, right: 10, left: -20, bottom: 42 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="type" angle={-25} textAnchor="end" interval={0} height={74} tick={{ fontSize: 12 }} />
                    <YAxis allowDecimals={false} />
                    <Tooltip />
                    <Legend />
                    {["Low", "Medium", "High", "Critical"].map((level) => (
                      <Bar key={level} dataKey={level} stackId="risk" fill={LEVEL_COLORS[level]} />
                    ))}
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </section>

            <section className="rounded border border-slate-200 bg-panel p-4 shadow-soft">
              <div className="mb-2 flex items-center gap-2">
                <BarChart3 size={18} className="text-[#1967d2]" aria-hidden="true" />
                <h2 className="text-base font-bold">Risk Score Comparison Between Locations</h2>
              </div>
              <p className="mb-4 text-sm leading-6 text-slate-600">
                This chart compares the country/region score aggregated from the visible grid cells under the selected disaster filter.
              </p>
              <div className="h-[320px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={comparisonData} margin={{ top: 10, right: 10, left: -20, bottom: 40 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="location" angle={-28} textAnchor="end" interval={0} height={70} tick={{ fontSize: 12 }} />
                    <YAxis domain={[0, 100]} />
                    <Tooltip formatter={(value) => [`${value}`, "Risk score"]} />
                    <Bar dataKey="risk" radius={[4, 4, 0, 0]}>
                      {comparisonData.map((entry) => (
                        <Cell key={entry.location} fill={LEVEL_COLORS[entry.level] || "#1967d2"} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </section>
          </div>
        </section>
      </main>

      {loading && (
        <div className="fixed inset-0 z-[1000] flex items-center justify-center bg-slate-950/20 backdrop-blur-sm">
          <div className="rounded border border-slate-200 bg-white px-5 py-4 text-sm font-semibold shadow-soft">
            Loading prototype dashboard data...
          </div>
        </div>
      )}
    </div>
  );
}

function DisasterIconMenu({ disasters, selected, onSelect }) {
  const menuItems = disasters.length
    ? disasters
    : GRID_DISASTERS.map((id) => ({ id, label: DISASTER_LABELS[id] }));

  return (
    <div>
      <span className="mb-2 block text-xs font-semibold uppercase text-slate-500">Disaster layer</span>
      <div className="grid grid-cols-2 gap-2">
        {menuItems.map((item) => {
          const Icon = DISASTER_ICONS[item.id] || Layers3;
          const isActive = selected === item.id;
          const accent = DISASTER_ACCENTS[item.id] || "#1967d2";

          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onSelect(item.id)}
              title={`Show ${item.label} risk surface`}
              className={`flex h-[58px] flex-col items-center justify-center gap-1 rounded border px-2 text-center text-[11px] font-bold transition ${
                isActive ? "bg-white shadow-soft" : "bg-slate-50 text-slate-600 hover:bg-white"
              }`}
              style={{
                borderColor: isActive ? accent : "#e2e8f0",
                color: isActive ? accent : undefined,
              }}
            >
              <Icon size={19} aria-hidden="true" />
              <span className="leading-tight">{item.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function RiskLegend() {
  return (
    <div className="absolute bottom-3 right-3 z-[500] rounded border border-slate-200 bg-white/95 p-3 text-xs shadow-soft">
      <p className="mb-2 font-bold text-slate-700">Risk score</p>
      <div className="flex items-center gap-2">
        {["Low", "Medium", "High", "Critical"].map((level) => (
          <div key={level} className="flex items-center gap-1">
            <span className="h-3 w-5 rounded-sm" style={{ backgroundColor: LEVEL_COLORS[level] }} />
            <span className="font-semibold text-slate-600">{level}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function buildOverviewGrid(records, targetCellDegrees = 0.42) {
  const boundedRecords = records
    .filter((record) => record.location?.bounds?.length === 2)
    .map((record) => {
      const [[south, west], [north, east]] = record.location.bounds;
      return {
        ...record,
        bounds: { south, west, north, east },
        boundsArea: Math.abs((north - south) * (east - west)),
      };
    });

  if (!boundedRecords.length) {
    return [];
  }

  const south = Math.min(...boundedRecords.map((record) => record.bounds.south));
  const west = Math.min(...boundedRecords.map((record) => record.bounds.west));
  const north = Math.max(...boundedRecords.map((record) => record.bounds.north));
  const east = Math.max(...boundedRecords.map((record) => record.bounds.east));
  const lonSpan = Math.max(0.1, east - west);
  const mercatorSouth = latitudeToMercator(south);
  const mercatorNorth = latitudeToMercator(north);
  const mercatorSpan = Math.max(0.1, mercatorNorth - mercatorSouth);
  let cellDegrees = Math.max(0.12, Math.min(1.2, targetCellDegrees));
  const maxCandidateCells = boundedRecords.length <= 1 ? 90000 : 260000;
  const estimatedCells = Math.ceil(lonSpan / cellDegrees) * Math.ceil(mercatorSpan / cellDegrees);
  if (estimatedCells > maxCandidateCells) {
    cellDegrees = Math.max(cellDegrees, Math.sqrt((lonSpan * mercatorSpan) / maxCandidateCells));
  }
  const columns = Math.max(12, Math.min(820, Math.ceil(lonSpan / cellDegrees)));
  const rows = Math.max(10, Math.min(520, Math.ceil(mercatorSpan / cellDegrees)));
  const lonStep = lonSpan / columns;
  const mercatorStep = mercatorSpan / rows;
  const cells = [];

  for (let row = 0; row < rows; row += 1) {
    const cellMercatorSouth = mercatorSouth + row * mercatorStep;
    const cellMercatorNorth = cellMercatorSouth + mercatorStep;
    const cellSouth = mercatorToLatitude(cellMercatorSouth);
    const cellNorth = mercatorToLatitude(cellMercatorNorth);
    const lat = mercatorToLatitude((cellMercatorSouth + cellMercatorNorth) / 2);
    for (let col = 0; col < columns; col += 1) {
      const cellWest = west + col * lonStep;
      const cellEast = cellWest + lonStep;
      const lon = (cellWest + cellEast) / 2;
      const record = findRecordForCell(boundedRecords, lat, lon);
      if (!record) {
        continue;
      }

      const score = overviewCellScore(record, lat, lon, row, col);
      const unavailable = record.risk_level === "Not Applicable" && Number(record.risk_score || 0) === 0;
      const level = unavailable ? "Not Applicable" : riskLevelFromScore(score);
      const locationName = record.locationName || record.location.name;
      const chancePercent = unavailable ? 0 : Number(record.chance_percent ?? (record.probability || 0) * 100 ?? 0);
      cells.push({
        id: `overview-${record.location.id}-${record.disaster_type}-${row}-${col}`,
        lat: Number(lat.toFixed(5)),
        lon: Number(lon.toFixed(5)),
        bounds: [
          [Number(cellSouth.toFixed(5)), Number(cellWest.toFixed(5))],
          [Number(cellNorth.toFixed(5)), Number(cellEast.toFixed(5))],
        ],
        disaster_type: record.disaster_type,
        risk_score: score,
        overall_risk_score: score,
        chance_percent: Number(clamp(chancePercent, 0, 95).toFixed(1)),
        severity_score: Number(record.severity_score || 0),
        confidence: record.confidence || "Moderate",
        raw_hazard: Number(record.raw_hazard || record.hazard_index || 0),
        time_window_days: record.time_window_days,
        event_definition: record.event_definition,
        risk_level: level,
        probability: Number((clamp(chancePercent, 0, 95) / 100).toFixed(4)),
        applicable: !unavailable,
        overview: true,
        location: record.location,
        locationName,
        reason: unavailable
          ? "No live API-backed risk score is available for this overview cell."
          : `${DISASTER_LABELS[record.disaster_type]} cell score is derived from ${locationName}'s live country/region record, a shore-aware land mask, and a small spatial variation factor.`,
        indicators: record.indicators || {},
        normalized_indicators: record.indicators || {},
        indicator_details: record.indicator_details || [],
        model_family: record.model_family,
        providers: record.providers || {},
        applicability: {
          applicable: !unavailable,
          reason: "This cell belongs to a continuous overview grid. Country scores are aggregated from land-masked grid cells whose centers fall inside that country/region.",
          conditions: [
            {
              label: "Cell center falls inside monitored country/region bounds",
              passed: true,
              value: locationName,
            },
            {
              label: "Live country/region API-backed risk record loaded",
              passed: !unavailable,
              value: record.weatherSource || "public API record",
            },
          ],
        },
      });
    }
  }

  return cells;
}

function findRecordForCell(records, lat, lon) {
  let match = null;
  for (const record of records) {
    const { south, west, north, east } = record.bounds;
    if (lat < south || lat > north || lon < west || lon > east) {
      continue;
    }
    if (!isApproximateLandCell(record.location.id, lat, lon)) {
      continue;
    }
    if (!match || record.boundsArea < match.boundsArea) {
      match = record;
    }
  }
  return match;
}

function overviewCellScore(record, lat, lon, row, col) {
  if (record.risk_level === "Not Applicable" && Number(record.risk_score || 0) === 0) {
    return 0;
  }
  const base = Number(record.risk_score || 0);
  const wave =
    Math.sin((lat + 90) * 0.29) * 0.45 +
    Math.cos((lon + 180) * 0.19) * 0.35 +
    Math.sin(row * 0.73 + col * 0.41) * 0.2;
  const variation = wave * 7;
  return Number(clamp(base + variation, 0, 100).toFixed(1));
}

function aggregateCountryGridScores(cells) {
  const grouped = new Map();
  for (const cell of cells) {
    if (!cell.location?.id) {
      continue;
    }
    const current = grouped.get(cell.location.id) || {
      count: 0,
      sum: 0,
      max: 0,
      applicableCount: 0,
      chanceSum: 0,
      severitySum: 0,
      confidenceScoreSum: 0,
    };
    current.count += 1;
    current.sum += Number(cell.risk_score || 0);
    current.max = Math.max(current.max, Number(cell.risk_score || 0));
    current.chanceSum += Number(cell.chance_percent || 0);
    current.severitySum += Number(cell.severity_score || 0);
    current.confidenceScoreSum += confidenceToNumber(cell.confidence);
    if (cell.applicable) {
      current.applicableCount += 1;
    }
    grouped.set(cell.location.id, current);
  }

  for (const aggregate of grouped.values()) {
    aggregate.average = aggregate.count ? Number((aggregate.sum / aggregate.count).toFixed(1)) : 0;
    aggregate.chancePercent = aggregate.count ? Number((aggregate.chanceSum / aggregate.count).toFixed(1)) : 0;
    aggregate.severityScore = aggregate.count ? Number((aggregate.severitySum / aggregate.count).toFixed(1)) : 0;
    aggregate.confidence = numberToConfidence(aggregate.count ? aggregate.confidenceScoreSum / aggregate.count : 0);
    aggregate.level = aggregate.applicableCount ? riskLevelFromScore(aggregate.average) : "Not Applicable";
  }

  return grouped;
}

function filterRenderableGrid(cells, viewport) {
  if (!cells.length) {
    return [];
  }

  const viewportCells = viewport
    ? cells.filter((cell) => cellBoundsIntersectViewport(cell.bounds, viewport))
    : cells;

  if (viewportCells.length <= MAX_RENDERED_GRID_CELLS) {
    return viewportCells;
  }

  const stride = Math.ceil(viewportCells.length / MAX_RENDERED_GRID_CELLS);
  return viewportCells.filter((_, index) => index % stride === 0).slice(0, MAX_RENDERED_GRID_CELLS);
}

function cellBoundsIntersectViewport(bounds, viewport) {
  if (!bounds || bounds.length !== 2) {
    return false;
  }
  const [[south, west], [north, east]] = bounds;
  const margin = Math.max(0.4, 4 / Math.max(1, viewport.zoom || 1));
  return (
    north >= viewport.south - margin &&
    south <= viewport.north + margin &&
    east >= viewport.west - margin &&
    west <= viewport.east + margin
  );
}

function riskLevelFromScore(score) {
  if (score <= 25) {
    return "Low";
  }
  if (score <= 50) {
    return "Medium";
  }
  if (score <= 75) {
    return "High";
  }
  return "Critical";
}

function confidenceToNumber(confidence) {
  if (confidence === "High") {
    return 3;
  }
  if (confidence === "Moderate") {
    return 2;
  }
  if (confidence === "Low") {
    return 1;
  }
  return 1.5;
}

function numberToConfidence(value) {
  if (value >= 2.5) {
    return "High";
  }
  if (value >= 1.5) {
    return "Moderate";
  }
  return "Low";
}

function clamp(value, minimum, maximum) {
  return Math.max(minimum, Math.min(maximum, value));
}

const MAX_MERCATOR_LATITUDE = 85.05112878;

function latitudeToMercator(lat) {
  const clampedLat = clamp(lat, -MAX_MERCATOR_LATITUDE, MAX_MERCATOR_LATITUDE);
  const radians = (clampedLat * Math.PI) / 180;
  return (Math.log(Math.tan(Math.PI / 4 + radians / 2)) * 180) / Math.PI;
}

function mercatorToLatitude(mercatorY) {
  return ((2 * Math.atan(Math.exp((mercatorY * Math.PI) / 180)) - Math.PI / 2) * 180) / Math.PI;
}

function gridCellStyle(cell) {
  const muted = cell.applicable === false || cell.risk_level === "Not Applicable";
  const color = muted ? LEVEL_COLORS["Not Applicable"] : LEVEL_COLORS[cell.risk_level] || "#f59f00";
  return {
    color,
    fillColor: color,
    fillOpacity: muted ? 0.08 : 0.16 + Math.min(0.36, Number(cell.risk_score || 0) / 260),
    opacity: muted ? 0.2 : 0.38,
    weight: cell.overview ? 0.7 : 1,
  };
}

function SelectField({ label, value, onChange, children }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-semibold uppercase text-slate-500">{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="h-10 w-full rounded border border-slate-300 bg-white px-3 text-sm outline-none focus:border-[#1967d2]"
      >
        {children}
      </select>
    </label>
  );
}

function SummaryCard({ icon, label, value, detail }) {
  return (
    <section className="rounded border border-slate-200 bg-panel p-4 shadow-soft">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase text-slate-500">{label}</p>
          <p className="mt-2 text-2xl font-bold">{value}</p>
          <p className="mt-1 text-sm text-muted">{detail}</p>
        </div>
        <div className="flex h-10 w-10 items-center justify-center rounded bg-[#e8f0fe] text-[#1967d2]">{icon}</div>
      </div>
    </section>
  );
}

function RiskBadge({ level }) {
  const isNotApplicable = level === "Not Applicable";
  return (
    <span
      className={`inline-flex items-center rounded px-2.5 py-1 text-xs font-bold ${isNotApplicable ? "border border-slate-300 text-slate-600" : "text-white"}`}
      style={{ backgroundColor: isNotApplicable ? "#f8fafc" : LEVEL_COLORS[level] || "#64748b" }}
    >
      {level}
    </span>
  );
}

function Metric({ label, value }) {
  return (
    <div className="rounded border border-slate-200 bg-white p-3">
      <p className="text-xs font-semibold uppercase text-slate-500">{label}</p>
      <p className="mt-1 break-words text-sm font-bold">{value}</p>
    </div>
  );
}

function ProviderStatusPanel({ providers }) {
  const entries = Object.entries(providers || {});
  if (!entries.length) {
    return null;
  }

  return (
    <section className="rounded border border-slate-200 bg-white p-3">
      <h3 className="mb-2 text-sm font-bold">External data providers</h3>
      <div className="grid gap-2 sm:grid-cols-2">
        {entries.map(([key, provider]) => (
          <div key={key} className="rounded border border-slate-100 bg-slate-50 p-2">
            <div className="flex items-start justify-between gap-2">
              <p className="text-xs font-semibold uppercase text-slate-500">{formatProviderName(key)}</p>
              <span
                className={`rounded px-2 py-0.5 text-[11px] font-bold ${
                  provider?.status === "unavailable"
                    ? "bg-red-100 text-red-700"
                    : provider?.status === "not_configured"
                      ? "bg-amber-100 text-amber-800"
                      : "bg-green-100 text-green-700"
                }`}
              >
                {providerStatusBadge(provider)}
              </span>
            </div>
            <p className="mt-1 break-words text-sm font-bold">{formatProviderStatus(provider)}</p>
            {provider?.reason && <p className="mt-1 text-xs leading-5 text-slate-500">{provider.reason}</p>}
          </div>
        ))}
      </div>
    </section>
  );
}

function GridCellPopup({ cell }) {
  const indicators = (cell.indicator_details || []).slice(0, 5);
  return (
    <div className="space-y-2">
      <p className="text-sm font-bold">{DISASTER_LABELS[cell.disaster_type]} grid cell</p>
      <p className="text-xs text-slate-600">Chance: {formatValue(cell.chance_percent ?? (cell.probability ?? 0) * 100)}%</p>
      <p className="text-xs text-slate-600">Severity if it happens: {formatValue(cell.severity_score)} / 100</p>
      <p className="text-xs text-slate-600">Overall risk score: {Number(cell.overall_risk_score ?? cell.risk_score).toFixed(1)}</p>
      <p className="text-xs text-slate-600">Confidence: {cell.confidence || "N/A"}</p>
      <RiskBadge level={cell.risk_level} />
      <div className="space-y-1 border-t border-slate-100 pt-2">
        <p className="text-xs font-bold text-slate-700">Actual input data</p>
        {indicators.length ? indicators.map((row) => (
          <div key={row.key} className="grid grid-cols-[1fr_auto] gap-x-3 gap-y-0.5 text-xs">
            <span className="text-slate-500">{row.label}</span>
            <span className="font-semibold">
              {formatValue(row.value)} {row.unit}
            </span>
            <span className="col-span-2 text-[11px] text-slate-400">
              Index contribution: {Number(row.normalized_value || 0).toFixed(1)} / 100
            </span>
          </div>
        )) : (
          Object.entries(cell.indicators || {}).slice(0, 5).map(([key, value]) => (
            <div key={key} className="flex justify-between gap-3 text-xs">
              <span className="capitalize text-slate-500">{key.replaceAll("_", " ")}</span>
              <span className="font-semibold">{formatValue(value)}</span>
            </div>
          ))
        )}
      </div>
      <p className="border-t border-slate-100 pt-2 text-xs leading-5 text-slate-600">{cell.reason}</p>
    </div>
  );
}

function MiniWeatherTable({ rows }) {
  if (!rows.length) {
    return null;
  }

  return (
    <div>
      <h3 className="mb-2 text-sm font-bold">Recent weather samples</h3>
      <div className="overflow-auto rounded border border-slate-200">
        <table className="w-full min-w-[420px] text-left text-xs">
          <thead className="bg-slate-50 text-slate-500">
            <tr>
              <th className="px-3 py-2">Date</th>
              <th className="px-3 py-2">Temp</th>
              <th className="px-3 py-2">Precip.</th>
              <th className="px-3 py-2">Wind</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.date} className="border-t border-slate-100">
                <td className="px-3 py-2">{row.date}</td>
                <td className="px-3 py-2">{row.temperature} C</td>
                <td className="px-3 py-2">{row.precipitation} mm</td>
                <td className="px-3 py-2">{row.wind_speed} km/h</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function formatValue(value) {
  if (typeof value === "number") {
    return Number(value).toFixed(Number.isInteger(value) ? 0 : 1);
  }
  return value ?? "N/A";
}

function formatProviderName(key) {
  return key.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatProviderStatus(provider = {}) {
  if (provider.source && provider.status !== "unavailable") {
    return provider.source;
  }
  if (provider.status === "configured") {
    return "Configured";
  }
  if (provider.status === "unavailable") {
    return "Unavailable";
  }
  return provider.source || provider.status || "Not configured";
}

function providerStatusBadge(provider = {}) {
  if (provider.status === "unavailable") {
    return "Error";
  }
  if (provider.status === "not_configured") {
    return "Setup";
  }
  return "On";
}

export default App;
