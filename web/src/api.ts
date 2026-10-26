export type Flight = {
  flight_id: string;
  flight_number?: string;
  callsign?: string;
  airline_icao?: string;
  airline_name?: string;
  aircraft_type?: string;
  manufacturer_family?: string;
  dep_airport_icao?: string;
  dep_airport_iata?: string;
  dep_airport_name?: string;
  arr_airport_icao?: string;
  arr_airport_iata?: string;
  arr_airport_name?: string;
  distance_km?: number;
  duration_h?: number;
  specs_is_complete?: boolean;
  utc_date?: string;
};

export type Spec = {
  typecode: string;
  manufacturer?: string;
  manufacturer_family?: string;
  model_name?: string;
  seats_typical?: number;
  mtow_kg?: number;
  engine_class?: string;
  fuel_burn_cruise_kg_per_h?: number;
  is_complete?: boolean;
  missing_fields?: string[];
};

export type EmissionRow = {
  flight_id?: string;
  flight_number?: string;
  callsign?: string;
  airline_icao?: string;
  airline_name?: string;
  aircraft_type?: string;
  fuel_kg_est?: number;
  nox_kg_est?: number;
  co2_kg_est?: number;
  estimate_status?: string;
};

export type AnalyticsPayload = {
  totals: {
    flights?: number;
    flights_estimated?: number;
    fuel_kg_est?: number;
    co2_kg_est?: number;
    nox_kg_est?: number;
  };
  by_airline_flights: {
    airline_icao?: string;
    airline_name?: string;
    flights: number;
  }[];
  by_type_flights: { aircraft_type: string; flights: number }[];
  by_family: { manufacturer_family: string; flights: number }[];
  by_airline_fleet: {
    airline_name?: string;
    airline_icao?: string;
    manufacturer_family?: string;
    aircraft_type?: string;
    model_name?: string;
    flights: number;
  }[];
  co2_by_airline: {
    airline_icao?: string;
    airline_name?: string;
    fuel_kg_est?: number;
    co2_kg_est?: number;
    nox_kg_est?: number;
  }[];
  co2_by_type: {
    aircraft_type: string;
    fuel_kg_est?: number;
    co2_kg_est?: number;
    nox_kg_est?: number;
  }[];
  flight_rows?: {
    airline_name?: string;
    airline_icao?: string;
    aircraft_type?: string;
    callsign?: string;
    max_baro_altitude_m?: number;
    max_velocity_ms?: number;
  }[];
  top_routes?: {
    dep_airport_iata?: string;
    arr_airport_iata?: string;
    dep_airport_icao?: string;
    arr_airport_icao?: string;
    dep_airport_name?: string;
    arr_airport_name?: string;
    flights: number;
  }[];
  fleet_mix?: {
    manufacturer_family?: string;
    aircraft_type?: string;
    model_name?: string;
    flights: number;
  }[];
  disclaimer: string;
};

export type EmissionsPayload = {
  count: number;
  totals: {
    fuel_kg_est?: number;
    nox_kg_est?: number;
    co2_kg_est?: number;
    flights_estimated?: number;
  };
  by_airline: {
    airline_icao: string;
    airline_name?: string;
    fuel_kg_est?: number;
    nox_kg_est?: number;
    co2_kg_est?: number;
  }[];
  by_aircraft_type: {
    aircraft_type: string;
    fuel_kg_est?: number;
    nox_kg_est?: number;
    co2_kg_est?: number;
  }[];
  emissions: EmissionRow[];
  disclaimer: string;
  note?: string;
};

/** Production / Vercel uses static JSON. Set VITE_USE_STATIC=1 to force static in dev. */
function useStaticData(): boolean {
  if (import.meta.env.VITE_USE_STATIC === "1") return true;
  if (import.meta.env.VITE_USE_STATIC === "0") return false;
  return import.meta.env.PROD;
}

/** Hit FastAPI directly (bypass Vite proxy) so a down API does not spam proxy errors. */
const LIVE_API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) || "http://127.0.0.1:8000";

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

async function tryLiveApi<T>(apiPath: string): Promise<T | null> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 900);
  try {
    const res = await fetch(`${LIVE_API_BASE}${apiPath}`, { signal: ctrl.signal });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

/** Prefer live FastAPI when up; otherwise web/public/data/*.json (no Vite /api proxy). */
async function getApiOrStatic<T>(apiPath: string, staticPath: string): Promise<T> {
  if (useStaticData()) {
    return getJson<T>(staticPath);
  }
  const live = await tryLiveApi<T>(apiPath);
  if (live != null) return live;
  return getJson<T>(staticPath);
}

export function fetchFlights(params: URLSearchParams = new URLSearchParams()) {
  return getApiOrStatic<{ count: number; flights: Flight[]; note?: string }>(
    `/api/flights?${params}`,
    "/data/flights.json"
  );
}

export async function fetchRoute(flightId: string) {
  // Routes need live track points — try FastAPI directly; no static fallback
  const path = `/api/routes/${encodeURIComponent(flightId)}`;
  const live = await tryLiveApi<{
    flight: Flight;
    track: { longitude: number; latitude: number; baro_altitude?: number; velocity?: number }[];
    disclaimer: string;
  }>(path);
  if (live) return live;
  throw new Error("Route track API is not running (start: python scripts/run_api.py)");
}

export function fetchSpecs(incompleteOnly = false) {
  return getApiOrStatic<{
    count: number;
    complete: number;
    incomplete: number;
    specs: Spec[];
  }>(`/api/specs?incomplete_only=${incompleteOnly}`, "/data/specs.json").then((d) => {
    if (!incompleteOnly) return d;
    const specs = (d.specs || []).filter((s) => !s.is_complete);
    return {
      ...d,
      count: specs.length,
      incomplete: specs.length,
      complete: 0,
      specs,
    };
  });
}

export function fetchEmissions() {
  return getApiOrStatic<EmissionsPayload>("/api/emissions", "/data/emissions.json");
}

export function fetchAnalytics() {
  return getApiOrStatic<AnalyticsPayload>("/api/analytics", "/data/analytics.json");
}

export function fetchMeta() {
  return getJson<{ generated_at?: string; disclaimer?: string; mode?: string }>(
    "/data/meta.json"
  ).catch(() => ({ disclaimer: undefined, generated_at: undefined }));
}
