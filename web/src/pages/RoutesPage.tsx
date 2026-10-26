import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { fetchFlights, fetchRoute, type Flight } from "../api";
import { formatFlightRoute, useAirportLabelMode } from "../airportLabels";
import { ensureAirportsCatalog, lookupAirportCoords } from "../airportsCatalog";
import { greatCircleLine, type LngLat } from "../geo";


function airportCode(f: Flight, which: "dep" | "arr"): string {
  const iata = which === "dep" ? f.dep_airport_iata : f.arr_airport_iata;
  const icao = which === "dep" ? f.dep_airport_icao : f.arr_airport_icao;
  return (iata || icao || "").trim().toUpperCase();
}

/** Hide flights without a usable OD (no ?→?, no UNKNOWN). */
function hasDisplayableRoute(f: Flight): boolean {
  const dep = airportCode(f, "dep");
  const arr = airportCode(f, "arr");
  if (!dep || !arr) return false;
  if (dep === "?" || arr === "?" || dep === "UNKNOWN" || arr === "UNKNOWN") return false;
  if (dep === arr) return false;
  return true;
}

function odLine(f: Flight): LngLat[] | null {
  const dep = lookupAirportCoords(f.dep_airport_icao, f.dep_airport_iata);
  const arr = lookupAirportCoords(f.arr_airport_icao, f.arr_airport_iata);
  if (!dep || !arr) return null;
  return greatCircleLine(dep.lon, dep.lat, arr.lon, arr.lat, 96);
}

function clearMapLayers(map: maplibregl.Map) {
  for (const id of ["od-line", "adsb-track", "airports"]) {
    if (map.getLayer(id)) map.removeLayer(id);
  }
  for (const id of ["od-line", "adsb-track", "airports"]) {
    if (map.getSource(id)) map.removeSource(id);
  }
}

function drawRoute(
  map: maplibregl.Map,
  opts: {
    odCoords: LngLat[] | null;
    dep?: { lon: number; lat: number } | null;
    arr?: { lon: number; lat: number } | null;
  }
) {
  const { odCoords, dep, arr } = opts;
  clearMapLayers(map);
  map.resize();

  const bounds = new maplibregl.LngLatBounds();
  let hasBounds = false;

  if (odCoords && odCoords.length >= 2) {
    map.addSource("od-line", {
      type: "geojson",
      data: {
        type: "Feature",
        properties: {},
        geometry: { type: "LineString", coordinates: odCoords },
      },
    });
    map.addLayer({
      id: "od-line",
      type: "line",
      source: "od-line",
      paint: {
        "line-color": "#c45c26",
        "line-width": 3.5,
        "line-opacity": 0.95,
      },
    });
    odCoords.forEach((c) => {
      bounds.extend(c);
      hasBounds = true;
    });
  }

  const points: GeoJSON.Feature[] = [];
  if (dep) {
    points.push({
      type: "Feature",
      properties: { role: "dep" },
      geometry: { type: "Point", coordinates: [dep.lon, dep.lat] },
    });
    bounds.extend([dep.lon, dep.lat]);
    hasBounds = true;
  }
  if (arr) {
    points.push({
      type: "Feature",
      properties: { role: "arr" },
      geometry: { type: "Point", coordinates: [arr.lon, arr.lat] },
    });
    bounds.extend([arr.lon, arr.lat]);
    hasBounds = true;
  }
  if (points.length) {
    map.addSource("airports", {
      type: "geojson",
      data: { type: "FeatureCollection", features: points },
    });
    map.addLayer({
      id: "airports",
      type: "circle",
      source: "airports",
      paint: {
        "circle-radius": 6,
        "circle-color": "#0b1c2c",
        "circle-stroke-width": 2,
        "circle-stroke-color": "#f2f7fb",
      },
    });
  }

  if (hasBounds && !bounds.isEmpty()) {
    map.fitBounds(bounds, { padding: 56, duration: 800, maxZoom: 6 });
  }
  requestAnimationFrame(() => map.resize());
}

export default function RoutesPage() {
  const { mode } = useAirportLabelMode();
  const { flightId } = useParams();
  const navigate = useNavigate();
  const mapRef = useRef<HTMLDivElement | null>(null);
  const mapObj = useRef<maplibregl.Map | null>(null);
  const [flights, setFlights] = useState<Flight[]>([]);
  const [meta, setMeta] = useState<Flight | null>(null);
  const [disclaimer, setDisclaimer] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchFlights(new URLSearchParams({ limit: "2000" }))
      .then((d) => {
        const usable = (d.flights || []).filter(hasDisplayableRoute);
        setFlights(usable);
      })
      .catch((e: Error) => setError(e.message));
  }, []);

  useEffect(() => {
    if (flightId && flights.length > 0 && !flights.some((f) => f.flight_id === flightId)) {
      navigate("/routes", { replace: true });
      setMeta(null);
    }
  }, [flightId, flights, navigate]);

  useEffect(() => {
    if (!flightId) return;
    setError(null);

    const fromList = flights.find((f) => f.flight_id === flightId) || null;
    if (fromList) setMeta(fromList);

    let cancelled = false;

    const paint = (flight: Flight, note: string) => {
      if (cancelled) return;

      setMeta(flight);
      const odCoords = odLine(flight);
      const dep = lookupAirportCoords(flight.dep_airport_icao, flight.dep_airport_iata);
      const arr = lookupAirportCoords(flight.arr_airport_icao, flight.arr_airport_iata);
      setDisclaimer(
        odCoords
          ? note
          : "Route line unavailable — departure or arrival airport not in the world catalog yet."
      );

      if (!mapRef.current) return;
      if (!mapObj.current) {
        const center: LngLat =
          odCoords?.[Math.floor((odCoords.length || 1) / 2)] || [8, 48];
        mapObj.current = new maplibregl.Map({
          container: mapRef.current,
          style: "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
          center,
          zoom: 3,
        });
      }
      const map = mapObj.current;
      const run = () =>
        drawRoute(map, {
          odCoords,
          dep: dep ? { lon: dep.lon, lat: dep.lat } : null,
          arr: arr ? { lon: arr.lon, lat: arr.lat } : null,
        });
      if (map.isStyleLoaded()) run();
      else map.once("load", run);
    };

    void ensureAirportsCatalog().then(() => {
      if (cancelled) return;
      fetchRoute(flightId)
        .then((data) => {
          paint(
            data.flight,
            data.disclaimer ||
              "Scheduled origin→destination as a great-circle path. Not an official airline schedule."
          );
        })
        .catch(() => {
          if (!fromList) {
            setError("Could not load route (API down and flight not in snapshot).");
            return;
          }
          paint(fromList, "Scheduled origin→destination (great circle).");
        });
    });

    return () => {
      cancelled = true;
    };
  }, [flightId, flights]);

  useEffect(() => {
    const onResize = () => mapObj.current?.resize();
    window.addEventListener("resize", onResize);
    const el = mapRef.current;
    const ro =
      el && typeof ResizeObserver !== "undefined"
        ? new ResizeObserver(() => mapObj.current?.resize())
        : null;
    if (el && ro) ro.observe(el);
    return () => {
      window.removeEventListener("resize", onResize);
      ro?.disconnect();
      mapObj.current?.remove();
      mapObj.current = null;
    };
  }, []);

  return (
    <div className="page page-routes">
      <h1>Routes</h1>
      {error && <div className="error">{error}</div>}
      <div className="toolbar">
        <select
          value={flightId || ""}
          onChange={(e) => navigate(e.target.value ? `/routes/${e.target.value}` : "/routes")}
        >
          <option value="">Select a flight</option>
          {flights.map((f) => (
            <option key={f.flight_id} value={f.flight_id}>
              {(f.flight_number || f.callsign) + " · " + formatFlightRoute(f, mode)}
            </option>
          ))}
        </select>
      </div>
      {flights.length === 0 && !error && (
        <p className="muted">No flights with a clear departure and arrival airport in this snapshot.</p>
      )}
      {meta && (
        <p className={mode === "full" ? "route-meta" : undefined}>
          <strong>{meta.airline_name || meta.airline_icao}</strong>
          {(() => {
            const type = (meta.aircraft_type || "").trim();
            const family = (meta.manufacturer_family || "").trim();
            const typeOk = type && type.toUpperCase() !== "UNKNOWN";
            const familyOk = family && family.toUpperCase() !== "UNKNOWN";
            if (!typeOk && !familyOk) return null;
            return (
              <>
                {" · "}
                {typeOk ? type : null}
                {typeOk && familyOk ? ` (${family})` : familyOk ? family : null}
              </>
            );
          })()}
          {" · "}
          {formatFlightRoute(meta, mode)}
        </p>
      )}
      <div className="map-panel" ref={mapRef} />
      <p className="disclaimer">
        {disclaimer || "Select a flight to load its route."}
      </p>
    </div>
  );
}
