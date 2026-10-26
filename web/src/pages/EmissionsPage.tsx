import { useEffect, useState } from "react";
import { fetchEmissions, type EmissionRow } from "../api";

export default function EmissionsPage() {
  const [totals, setTotals] = useState<{
    fuel_kg_est?: number;
    nox_kg_est?: number;
    co2_kg_est?: number;
    flights_estimated?: number;
  }>({});
  const [byAirline, setByAirline] = useState<
    {
      airline_icao: string;
      airline_name?: string;
      fuel_kg_est?: number;
      nox_kg_est?: number;
      co2_kg_est?: number;
    }[]
  >([]);
  const [byType, setByType] = useState<
    { aircraft_type: string; fuel_kg_est?: number; nox_kg_est?: number; co2_kg_est?: number }[]
  >([]);
  const [rows, setRows] = useState<EmissionRow[]>([]);
  const [disclaimer, setDisclaimer] = useState("");
  const [note, setNote] = useState<string | undefined>();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchEmissions()
      .then((d) => {
        setTotals(d.totals || {});
        setByAirline(d.by_airline || []);
        setByType(d.by_aircraft_type || []);
        setRows(d.emissions || []);
        setDisclaimer(d.disclaimer);
        setNote(d.note);
      })
      .catch((e: Error) => setError(e.message));
  }, []);

  return (
    <div className="page">
      <h1>Emissions estimates</h1>
      <p className="lede">Estimated fuel, CO₂ and NOx per flight.</p>
      {error && <div className="error">{error}</div>}
      {note && <p className="muted">{note}</p>}
      <div className="stats">
        <div className="stat">
          <strong>{totals.flights_estimated ?? 0}</strong>
          <span>Flights estimated</span>
        </div>
        <div className="stat">
          <strong>
            {totals.fuel_kg_est != null ? Math.round(totals.fuel_kg_est).toLocaleString() : "—"}
          </strong>
          <span>Fuel kg (est.)</span>
        </div>
        <div className="stat">
          <strong>
            {totals.co2_kg_est != null ? Math.round(totals.co2_kg_est).toLocaleString() : "—"}
          </strong>
          <span>CO₂ kg (est.)</span>
        </div>
        <div className="stat">
          <strong>{totals.nox_kg_est != null ? totals.nox_kg_est.toFixed(1) : "—"}</strong>
          <span>NOx kg (est.)</span>
        </div>
      </div>

      <h2 style={{ fontFamily: "var(--font-display)", letterSpacing: "0.03em" }}>Per flight</h2>
      <div className="table-wrap" style={{ marginBottom: "1.5rem" }}>
        <table>
          <thead>
            <tr>
              <th>Flight</th>
              <th>Airline</th>
              <th>Type</th>
              <th>Fuel kg</th>
              <th>CO₂ kg</th>
              <th>NOx kg</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.flight_id || `${r.callsign}-${r.aircraft_type}`}>
                <td>{r.flight_number || r.callsign || r.flight_id}</td>
                <td>
                  {r.airline_name || r.airline_icao} ({r.airline_icao})
                </td>
                <td>{r.aircraft_type}</td>
                <td>
                  {r.fuel_kg_est != null ? Math.round(r.fuel_kg_est).toLocaleString() : "—"}
                </td>
                <td>
                  {r.co2_kg_est != null ? Math.round(r.co2_kg_est).toLocaleString() : "—"}
                </td>
                <td>{r.nox_kg_est != null ? r.nox_kg_est.toFixed(2) : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2 style={{ fontFamily: "var(--font-display)", letterSpacing: "0.03em" }}>By airline</h2>
      <div className="table-wrap" style={{ marginBottom: "1.5rem" }}>
        <table>
          <thead>
            <tr>
              <th>Airline</th>
              <th>Fuel kg</th>
              <th>CO₂ kg</th>
              <th>NOx kg</th>
            </tr>
          </thead>
          <tbody>
            {byAirline.map((r) => (
              <tr key={r.airline_icao}>
                <td>
                  {r.airline_name || r.airline_icao} ({r.airline_icao})
                </td>
                <td>{r.fuel_kg_est != null ? Math.round(r.fuel_kg_est).toLocaleString() : "—"}</td>
                <td>{r.co2_kg_est != null ? Math.round(r.co2_kg_est).toLocaleString() : "—"}</td>
                <td>{r.nox_kg_est != null ? r.nox_kg_est.toFixed(2) : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2 style={{ fontFamily: "var(--font-display)", letterSpacing: "0.03em" }}>By aircraft type</h2>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Type</th>
              <th>Fuel kg</th>
              <th>CO₂ kg</th>
              <th>NOx kg</th>
            </tr>
          </thead>
          <tbody>
            {byType.map((r) => (
              <tr key={r.aircraft_type}>
                <td>{r.aircraft_type}</td>
                <td>{r.fuel_kg_est != null ? Math.round(r.fuel_kg_est).toLocaleString() : "—"}</td>
                <td>{r.co2_kg_est != null ? Math.round(r.co2_kg_est).toLocaleString() : "—"}</td>
                <td>{r.nox_kg_est != null ? r.nox_kg_est.toFixed(2) : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="disclaimer">{disclaimer}</p>
    </div>
  );
}
