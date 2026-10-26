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
  arr_airport_icao?: string;
  arr_airport_iata?: string;
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

/** Production / Vercel uses static JSON; local vite proxy uses FastAPI unless VITE_USE_STATIC=1. */
function useStaticData(): boolean {
  if (import.meta.env.VITE_USE_STATIC === "1") return true;
  if (import.meta.env.VITE_USE_STATIC === "0") return false;
  return import.meta.env.PROD;
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export function fetchFlights(params: URLSearchParams = new URLSearchParams()) {
  if (useStaticData()) {
    return getJson<{ count: number; flights: Flight[]; note?: string }>("/data/flights.json");
  }
  return getJson<{ count: number; flights: Flight[]; note?: string }>(
    `/api/flights?${params}`
  );
}

export function fetchRoute(flightId: string) {
  // Routes need live track points — not in static snapshot; call API when available
  return getJson<{
    flight: Flight;
    track: { longitude: number; latitude: number; baro_altitude?: number; velocity?: number }[];
    disclaimer: string;
  }>(`/api/routes/${encodeURIComponent(flightId)}`);
}

export function fetchSpecs(incompleteOnly = false) {
  if (useStaticData()) {
    return getJson<{
      count: number;
      complete: number;
      incomplete: number;
      specs: Spec[];
    }>("/data/specs.json").then((d) => {
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
  return getJson<{
    count: number;
    complete: number;
    incomplete: number;
    specs: Spec[];
  }>(`/api/specs?incomplete_only=${incompleteOnly}`);
}

export function fetchEmissions() {
  if (useStaticData()) {
    return getJson<EmissionsPayload>("/data/emissions.json");
  }
  return getJson<EmissionsPayload>("/api/emissions");
}

export function fetchAnalytics() {
  if (useStaticData()) {
    return getJson<AnalyticsPayload>("/data/analytics.json");
  }
  return getJson<AnalyticsPayload>("/api/analytics");
}

export function fetchMeta() {
  return getJson<{ generated_at?: string; disclaimer?: string; mode?: string }>(
    "/data/meta.json"
  ).catch(() => ({ disclaimer: undefined, generated_at: undefined }));
}
