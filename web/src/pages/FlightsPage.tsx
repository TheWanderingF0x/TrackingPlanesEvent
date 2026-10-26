import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { fetchFlights, type Flight } from "../api";
import { formatFlightRoute, useAirportLabelMode } from "../airportLabels";

function norm(value?: string | null): string {
  return (value || "").trim();
}

const EXCLUDED_FAMILIES = new Set(["other", "unknown"]);
const EXCLUDED_TYPES = new Set(["unknown", "nan", "none", ""]);

function hasKnownAircraft(f: Flight): boolean {
  const family = norm(f.manufacturer_family).toLowerCase();
  const type = norm(f.aircraft_type).toLowerCase();
  if (EXCLUDED_FAMILIES.has(family)) return false;
  if (EXCLUDED_TYPES.has(type)) return false;
  return true;
}

function flightRowKey(f: Flight, index: number): string {
  // flight_id alone is not unique in the lake — duplicates break React row updates/filters
  return [f.flight_id, f.callsign, f.utc_date, f.aircraft_type, String(index)].join("|");
}

export default function FlightsPage() {
  const { mode } = useAirportLabelMode();
  const [allFlights, setAllFlights] = useState<Flight[]>([]);
  const [note, setNote] = useState<string | undefined>();
  const [error, setError] = useState<string | null>(null);
  const [airline, setAirline] = useState("");
  const [family, setFamily] = useState("");

  useEffect(() => {
    let cancelled = false;
    fetchFlights(new URLSearchParams({ limit: "2000" }))
      .then((data) => {
        if (cancelled) return;
        setAllFlights((data.flights || []).filter(hasKnownAircraft));
        setNote(data.note);
      })
      .catch((e: Error) => {
        if (!cancelled) setError(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const airlines = useMemo(
    () =>
      [...new Set(allFlights.map((f) => norm(f.airline_icao)).filter(Boolean))].sort(),
    [allFlights]
  );
  const families = useMemo(
    () =>
      [
        ...new Set(allFlights.map((f) => norm(f.manufacturer_family)).filter(Boolean)),
      ].sort(),
    [allFlights]
  );

  const flights = useMemo(() => {
    return allFlights.filter((f) => {
      if (airline && norm(f.airline_icao) !== airline) return false;
      if (family && norm(f.manufacturer_family) !== family) return false;
      return true;
    });
  }, [allFlights, airline, family]);

  const filterKey = `${airline}::${family}`;

  return (
    <div className="page">
      <h1>Flights</h1>
      <p className="lede">
        Callsign / flight number, airline, aircraft family, and estimated origin–destination.
      </p>
      {error && <div className="error">{error}</div>}
      {note && <p className="muted">{note}</p>}
      <div className="toolbar">
        <select
          aria-label="Airline"
          value={airline}
          onChange={(e) => setAirline(e.target.value)}
        >
          <option value="">All airlines</option>
          {airlines.map((a) => (
            <option key={a} value={a}>
              {a}
            </option>
          ))}
        </select>
        <select
          aria-label="Manufacturer family"
          value={family}
          onChange={(e) => setFamily(e.target.value)}
        >
          <option value="">All manufacturers</option>
          {families.map((name) => (
            <option key={name} value={name}>
              {name}
            </option>
          ))}
        </select>
      </div>
      <p className="muted">
        Showing {flights.length} of {allFlights.length} flights
        {family ? ` · family: ${family}` : ""}
        {airline ? ` · airline: ${airline}` : ""}
      </p>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Flight</th>
              <th>Airline</th>
              <th>Type</th>
              <th>Family</th>
              <th>Route</th>
              <th />
            </tr>
          </thead>
          <tbody key={filterKey}>
            {flights.length === 0 ? (
              <tr>
                <td colSpan={6} className="muted">
                  No flights match these filters. Choose All airlines / All manufacturers to reset.
                </td>
              </tr>
            ) : (
              flights.map((f, index) => (
                <tr key={flightRowKey(f, index)}>
                  <td>{f.flight_number || f.callsign}</td>
                  <td>
                    {f.airline_name} ({f.airline_icao})
                  </td>
                  <td>{f.aircraft_type}</td>
                  <td>{f.manufacturer_family}</td>
                  <td className={mode === "full" ? "route-cell" : undefined}>
                    {formatFlightRoute(f, mode)}
                  </td>
                  <td>
                    <Link to={`/routes/${f.flight_id}`}>Map</Link>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      <p className="disclaimer">
        Routes prefer scheduled origin/destination from the flight callsign when available;
        otherwise nearest-airport estimates from ADS-B. Not an official airline schedule.
      </p>
    </div>
  );
}
