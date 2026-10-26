import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import type { Flight } from "./api";
import { lookupAirportName } from "./airportsCatalog";

export type AirportLabelMode = "full" | "icao";

const STORAGE_KEY = "tp_airport_label_mode";

type Ctx = {
  mode: AirportLabelMode;
  setMode: (m: AirportLabelMode) => void;
};

const AirportLabelContext = createContext<Ctx | null>(null);

function readStoredMode(): AirportLabelMode {
  try {
    return localStorage.getItem(STORAGE_KEY) === "icao" ? "icao" : "full";
  } catch {
    return "full";
  }
}

export function AirportLabelProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<AirportLabelMode>(readStoredMode);

  const setMode = (m: AirportLabelMode) => {
    setModeState(m);
    try {
      localStorage.setItem(STORAGE_KEY, m);
    } catch {
      /* ignore */
    }
  };

  useEffect(() => {
    setModeState(readStoredMode());
  }, []);

  return (
    <AirportLabelContext.Provider value={{ mode, setMode }}>
      {children}
    </AirportLabelContext.Provider>
  );
}

export function useAirportLabelMode(): Ctx {
  const ctx = useContext(AirportLabelContext);
  if (!ctx) {
    throw new Error("useAirportLabelMode requires AirportLabelProvider");
  }
  return ctx;
}

export function AirportLabelToggle() {
  const { mode, setMode } = useAirportLabelMode();
  return (
    <div className="airport-toggle" role="group" aria-label="Airport label mode">
      <button
        type="button"
        className={mode === "full" ? "active" : ""}
        onClick={() => setMode("full")}
        title="Full place / airport names (no codes)"
      >
        Full names
      </button>
      <button
        type="button"
        className={mode === "icao" ? "active" : ""}
        onClick={() => setMode("icao")}
        title="ICAO codes only"
      >
        ICAO
      </button>
    </div>
  );
}

type AirportSide = {
  icao?: string | null;
  iata?: string | null;
  name?: string | null;
};

/** True if value looks like an airport code, not a place name. */
function looksLikeCode(value: string): boolean {
  const v = value.trim().toUpperCase();
  if (!v) return true;
  // IATA 3 / ICAO 4 letter codes
  if (/^[A-Z0-9]{3,4}$/.test(v)) return true;
  return false;
}

function cleanField(value?: string | null): string {
  const v = (value || "").trim();
  if (!v || ["nan", "none", "null", "undefined", "?"].includes(v.toLowerCase())) {
    return "";
  }
  return v;
}

export function formatAirportSide(side: AirportSide, mode: AirportLabelMode): string {
  const icao = cleanField(side.icao).toUpperCase();
  const iata = cleanField(side.iata).toUpperCase();
  const rawName = cleanField(side.name);
  if (mode === "icao") {
    return icao || iata || "?";
  }
  // Full-names: prefer payload name, else catalog from airports_europe.csv
  if (rawName && !looksLikeCode(rawName)) {
    return rawName;
  }
  const fromCatalog = lookupAirportName(icao || null, iata || null);
  if (fromCatalog) {
    return fromCatalog;
  }
  return "Unknown place";
}

export function formatFlightRoute(f: Flight, mode: AirportLabelMode): string {
  const dep = formatAirportSide(
    {
      icao: f.dep_airport_icao,
      iata: f.dep_airport_iata,
      name: f.dep_airport_name,
    },
    mode
  );
  const arr = formatAirportSide(
    {
      icao: f.arr_airport_icao,
      iata: f.arr_airport_iata,
      name: f.arr_airport_name,
    },
    mode
  );
  return `${dep} → ${arr}`;
}
