import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { fetchFlights, fetchRoute, type Flight } from "../api";
import { formatFlightRoute, useAirportLabelMode } from "../airportLabels";

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
    // High limit so OD-complete flights are not cut off by the default API 500 cap
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
    fetchRoute(flightId)
      .then((data) => {
        setMeta(data.flight);
        setDisclaimer(data.disclaimer);
        const coords = data.track
          .filter((p) => p.longitude != null && p.latitude != null)
          .map((p) => [p.longitude, p.latitude] as [number, number]);

        if (!mapRef.current) return;
        if (!mapObj.current) {
          mapObj.current = new maplibregl.Map({
            container: mapRef.current,
            style: "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
            center: coords[0] || [8, 48],
            zoom: 4,
          });
        }
        const map = mapObj.current;
        const draw = () => {
          map.resize();
          if (map.getLayer("route-line")) map.removeLayer("route-line");
          if (map.getSource("route")) map.removeSource("route");
          if (coords.length < 2) return;
          map.addSource("route", {
            type: "geojson",
            data: {
              type: "Feature",
              properties: {},
              geometry: { type: "LineString", coordinates: coords },
            },
          });
          map.addLayer({
            id: "route-line",
            type: "line",
            source: "route",
            paint: {
              "line-color": "#c45c26",
              "line-width": 3,
            },
          });
          const bounds = coords.reduce(
            (b, c) => b.extend(c),
            new maplibregl.LngLatBounds(coords[0], coords[0])
          );
          map.fitBounds(bounds, { padding: 48, duration: 800 });
          requestAnimationFrame(() => map.resize());
        };
        if (map.isStyleLoaded()) draw();
        else map.once("load", draw);
      })
      .catch((e: Error) => setError(e.message));
  }, [flightId]);

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
        {disclaimer || "Select a flight to load its track."}
        {" "}
        Some data may be incomplete (aircraft type, airports, or track coverage).
      </p>
    </div>
  );
}
