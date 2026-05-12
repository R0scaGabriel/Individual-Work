import axios from "axios";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 20000,
});

export async function getLocations() {
  const response = await api.get("/api/locations");
  return response.data;
}

export async function getDisasters() {
  const response = await api.get("/api/disasters");
  return response.data;
}

export async function getRiskForLocation(location) {
  const response = await api.get("/api/risk/all", {
    params: { lat: location.lat, lon: location.lon, strict_real: true },
  });
  return response.data;
}

export async function getRiversForLocation(location, radiusKm = 15) {
  const boundsParams = boundsToParams(location.bounds);
  const response = await api.get("/api/map/rivers", {
    params: {
      lat: location.lat,
      lon: location.lon,
      radius_km: radiusKm,
      strict_real: true,
      ...boundsParams,
    },
  });
  return response.data;
}

export async function getRiskGrid(disasterType, location, radiusKm = 35, resolution = 7) {
  const boundsParams = boundsToParams(location.bounds);
  const response = await api.get("/api/risk/grid", {
    params: {
      disaster: disasterType,
      lat: location.lat,
      lon: location.lon,
      radius_km: radiusKm,
      resolution,
      strict_real: true,
      ...boundsParams,
    },
    timeout: 45000,
  });
  return response.data;
}

export async function getEarthquakeMap(location, radiusKm = 1500) {
  const response = await api.get("/api/map/earthquakes", {
    params: { lat: location.lat, lon: location.lon, radius_km: radiusKm, strict_real: true },
  });
  return response.data;
}

function boundsToParams(bounds) {
  if (!bounds || bounds.length !== 2) {
    return {};
  }
  return {
    south: bounds[0][0],
    west: bounds[0][1],
    north: bounds[1][0],
    east: bounds[1][1],
  };
}
