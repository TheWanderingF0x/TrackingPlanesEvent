import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { fetchFlights, type Flight } from "../api";

export default function FlightsPage() {
  const [flights, setFlights] = useState<Flight[]>([]);
  const [note, setNote] = useState<string | undefined>();
  const [error, setError] = useState<string | null>(null);
  const [airline, setAirline] = useState("");
  const [family, setFamily] = useState("");

  useEffect(() => {
    const params = new URLSearchParams();
    if (airline) params.set("airline", airline);
    if (family) params.set("manufacturer", family);
    fetchFlights(params)
      .then((data) => {
        setFlights(data.flights);
        setNote(data.note);
      })
      .catch((e: Error) => setError(e.message));
  }, [airline, family]);

  const airlines = useMemo(
    () =>
      [...new Set(flights.map((f) => f.airline_icao).filter(Boolean) as string[])].sort(),
    [flights]
  );
  const families = useMemo(
    () =>
      [
        ...new Set(flights.map((f) => f.manufacturer_family).filter(Boolean) as string[]),
      ].sort(),
    [flights]
  );

  return (
    <div className="page">
      <h1>Flights</h1>
      <p className="lede">
        Callsign / flight number, airline, aircraft family, and estimated origin–destination.
      </p>
      {error && <div className="error">{error}</div>}
      {note && <p className="muted">{note}</p>}
      <div className="toolbar">
        <select value={airline} onChange={(e) => setAirline(e.target.value)}>
          <option value="">All airlines</option>
          {airlines.map((a) => (
            <option key={a} value={a}>
              {a}
            </option>
          ))}
        </select>
        <select value={family} onChange={(e) => setFamily(e.target.value)}>
          <option value="">All manufacturers</option>
          {families.map((f) => (
            <option key={f} value={f}>
              {f}
            </option>
          ))}
        </select>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Flight</th>
              <th>Airline</th>
              <th>Type</th>
              <th>Family</th>
              <th>Route</th>
              <th>Km</th>
              <th>Specs</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {flights.map((f) => (
              <tr key={f.flight_id}>
                <td>{f.flight_number || f.callsign}</td>
                <td>
                  {f.airline_name} ({f.airline_icao})
                </td>
                <td>{f.aircraft_type}</td>
                <td>{f.manufacturer_family}</td>
                <td>
                  {(f.dep_airport_iata || f.dep_airport_icao || "?") +
                    " → " +
                    (f.arr_airport_iata || f.arr_airport_icao || "?")}
                </td>
                <td>{f.distance_km?.toFixed?.(0) ?? "—"}</td>
                <td>
                  {f.specs_is_complete ? (
                    <span className="badge badge-ok">complete</span>
                  ) : (
                    <span className="badge badge-warn">incomplete</span>
                  )}
                </td>
                <td>
                  <Link to={`/routes/${f.flight_id}`}>Map</Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="disclaimer">
        Origin/destination airports are nearest-airport estimates from ADS-B positions, not
        official schedules.
      </p>
    </div>
  );
}
