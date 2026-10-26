import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { fetchFlights, type Flight } from "../api";
import { formatFlightRoute, useAirportLabelMode } from "../airportLabels";

export default function FlightsPage() {
  const { mode } = useAirportLabelMode();
  const [allFlights, setAllFlights] = useState<Flight[]>([]);
  const [note, setNote] = useState<string | undefined>();
  const [error, setError] = useState<string | null>(null);
  const [airline, setAirline] = useState("");
  const [family, setFamily] = useState("");

  useEffect(() => {
    fetchFlights(new URLSearchParams({ limit: "2000" }))
      .then((data) => {
        setAllFlights(data.flights || []);
        setNote(data.note);
      })
      .catch((e: Error) => setError(e.message));
  }, []);

  // Options always from the full snapshot — selecting ATR must not hide Boeing, etc.
  const airlines = useMemo(
    () =>
      [...new Set(allFlights.map((f) => f.airline_icao).filter(Boolean) as string[])].sort(),
    [allFlights]
  );
  const families = useMemo(
    () =>
      [
        ...new Set(
          allFlights.map((f) => f.manufacturer_family).filter(Boolean) as string[]
        ),
      ].sort(),
    [allFlights]
  );

  const flights = useMemo(() => {
    return allFlights.filter((f) => {
      if (airline && f.airline_icao !== airline) return false;
      if (family && f.manufacturer_family !== family) return false;
      return true;
    });
  }, [allFlights, airline, family]);

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
                <td className={mode === "full" ? "route-cell" : undefined}>
                  {formatFlightRoute(f, mode)}
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
        Routes prefer scheduled origin/destination from the flight callsign when available;
        otherwise nearest-airport estimates from ADS-B. Not an official airline schedule.
      </p>
    </div>
  );
}
