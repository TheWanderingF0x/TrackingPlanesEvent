/** Auto-generated — do not edit by hand. */
/** Run: python scripts/sync_world_airports.py && python scripts/generate_airports_catalog.py */

export type AirportCoords = { lat: number; lon: number; name?: string };

type CatalogPayload = {
  names: Record<string, string>;
  coords: Record<string, AirportCoords>;
};

let names: Record<string, string> = {};
let coords: Record<string, AirportCoords> = {};
let loadPromise: Promise<void> | null = null;

/** Preload world airport names/coords from /data/airports.json (call once at app start). */
export function ensureAirportsCatalog(): Promise<void> {
  if (Object.keys(coords).length > 0) return Promise.resolve();
  if (loadPromise) return loadPromise;
  loadPromise = fetch("/data/airports.json")
    .then((r) => {
      if (!r.ok) throw new Error(`airports.json ${r.status}`);
      return r.json() as Promise<CatalogPayload>;
    })
    .then((data) => {
      names = data.names || {};
      coords = data.coords || {};
    })
    .catch(() => {
      names = {};
      coords = {};
    });
  return loadPromise;
}

export function lookupAirportName(icao?: string | null, iata?: string | null): string | null {
  const a = (icao || "").trim().toUpperCase();
  const b = (iata || "").trim().toUpperCase();
  if (a && names[a]) return names[a];
  if (b && names[b]) return names[b];
  return null;
}

export function lookupAirportCoords(icao?: string | null, iata?: string | null): AirportCoords | null {
  const a = (icao || "").trim().toUpperCase();
  const b = (iata || "").trim().toUpperCase();
  if (a && coords[a]) return coords[a];
  if (b && coords[b]) return coords[b];
  return null;
}
