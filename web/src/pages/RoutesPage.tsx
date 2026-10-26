import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { fetchFlights, fetchRoute, type Flight } from "../api";

export default function RoutesPage() {
  const { flightId } = useParams();
  const navigate = useNavigate();
  const mapRef = useRef<HTMLDivElement | null>(null);
  const mapObj = useRef<maplibregl.Map | null>(null);
  const [flights, setFlights] = useState<Flight[]>([]);
  const [meta, setMeta] = useState<Flight | null>(null);
  const [disclaimer, setDisclaimer] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchFlights()
      .then((d) => setFlights(d.flights))
      .catch((e: Error) => setError(e.message));
  }, []);

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
    return () => {
      window.removeEventListener("resize", onResize);
      mapObj.current?.remove();
      mapObj.current = null;
    };
  }, []);

  return (
    <div className="page">
      <h1>Routes</h1>
      <p className="lede">Track points between estimated departure and arrival.</p>
      {error && <div className="error">{error}</div>}
      <div className="toolbar">
        <select
          value={flightId || ""}
          onChange={(e) => navigate(e.target.value ? `/routes/${e.target.value}` : "/routes")}
        >
          <option value="">Select a flight</option>
          {flights.map((f) => (
            <option key={f.flight_id} value={f.flight_id}>
              {(f.flight_number || f.callsign) +
                " · " +
                (f.dep_airport_iata || "?") +
                "→" +
                (f.arr_airport_iata || "?")}
            </option>
          ))}
        </select>
      </div>
      {meta && (
        <p>
          <strong>{meta.airline_name}</strong> · {meta.aircraft_type} ({meta.manufacturer_family}) ·{" "}
          {meta.dep_airport_icao} → {meta.arr_airport_icao}
        </p>
      )}
      <div className="map-panel" ref={mapRef} />
      <p className="disclaimer">
        {disclaimer || "Select a flight to load its track."}
      </p>
    </div>
  );
}
