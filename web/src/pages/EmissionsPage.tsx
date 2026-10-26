import { useEffect, useState } from "react";
import { fetchEmissions, type EmissionRow } from "../api";

/** Rows shown per page in the Per flight panel (fixed viewport). */
const PAGE_SIZE = 25;

function fmtKg(n?: number | null, digits = 0): string {
  if (n == null || Number.isNaN(n)) return "—";
  return digits > 0 ? n.toFixed(digits) : Math.round(n).toLocaleString();
}

function flightLabel(r: EmissionRow): string {
  return String(r.flight_number || r.callsign || r.flight_id || "—");
}

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
  const [page, setPage] = useState(0);
  const [disclaimer, setDisclaimer] = useState("");
  const [note, setNote] = useState<string | undefined>();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchEmissions()
      .then((d) => {
        if (cancelled) return;
        setTotals(d.totals || {});
        setByAirline(d.by_airline || []);
        setByType(d.by_aircraft_type || []);
        setRows(d.emissions || []);
        setPage(0);
        setDisclaimer(d.disclaimer);
        setNote(d.note);
      })
      .catch((e: Error) => {
        if (!cancelled) setError(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const pageCount = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  const safePage = Math.min(Math.max(0, page), pageCount - 1);
  const start = safePage * PAGE_SIZE;
  const pageRows = rows.slice(start, start + PAGE_SIZE);
  const rangeStart = rows.length === 0 ? 0 : start + 1;
  const rangeEnd = Math.min(start + PAGE_SIZE, rows.length);

  const goPrev = () => setPage((p) => Math.max(0, p - 1));
  const goNext = () => setPage((p) => Math.min(pageCount - 1, p + 1));

  return (
    <div className="page page-emissions">
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
          <strong>{fmtKg(totals.fuel_kg_est)}</strong>
          <span>Fuel kg (est.)</span>
        </div>
        <div className="stat">
          <strong>{fmtKg(totals.co2_kg_est)}</strong>
          <span>CO₂ kg (est.)</span>
        </div>
        <div className="stat">
          <strong>{totals.nox_kg_est != null ? totals.nox_kg_est.toFixed(1) : "—"}</strong>
          <span>NOx kg (est.)</span>
        </div>
      </div>

      <div className="emissions-grid">
        <section className="emissions-panel emissions-panel-paged">
          <div className="emissions-panel-head">
            <h2>Per flight</h2>
            <div className="pager" role="navigation" aria-label="Per flight pages">
              <button type="button" disabled={safePage <= 0} onClick={goPrev}>
                Prev
              </button>
              <span className="muted">
                {rows.length === 0 ? "No rows" : `${rangeStart}–${rangeEnd} of ${rows.length}`}
              </span>
              <button
                type="button"
                disabled={safePage >= pageCount - 1 || rows.length === 0}
                onClick={goNext}
              >
                Next
              </button>
            </div>
          </div>
          <div className="table-wrap emissions-paged">
            <table>
              <thead>
                <tr>
                  <th>Flight</th>
                  <th>Airline</th>
                  <th>Type</th>
                  <th>Fuel</th>
                  <th>CO₂</th>
                  <th>NOx</th>
                </tr>
              </thead>
              {/* Remount each page — duplicate flight_id keys were leaving stale rows */}
              <tbody key={`emissions-page-${safePage}`}>
                {pageRows.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="muted">
                      No per-flight estimates yet.
                    </td>
                  </tr>
                ) : (
                  pageRows.map((r, i) => (
                    <tr key={`${safePage}-${i}-${r.flight_id}-${r.callsign}-${r.aircraft_type}`}>
                      <td title={flightLabel(r)}>{flightLabel(r)}</td>
                      <td title={r.airline_name || r.airline_icao}>{r.airline_icao}</td>
                      <td>{r.aircraft_type}</td>
                      <td>{fmtKg(r.fuel_kg_est)}</td>
                      <td>{fmtKg(r.co2_kg_est)}</td>
                      <td>{fmtKg(r.nox_kg_est, 2)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>

        <section className="emissions-panel">
          <h2>By airline</h2>
          <div className="table-wrap emissions-scroll">
            <table>
              <thead>
                <tr>
                  <th>Airline</th>
                  <th>Fuel</th>
                  <th>CO₂</th>
                  <th>NOx</th>
                </tr>
              </thead>
              <tbody>
                {byAirline.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="muted">
                      No airline totals yet.
                    </td>
                  </tr>
                ) : (
                  byAirline.map((r) => (
                    <tr key={r.airline_icao}>
                      <td title={`${r.airline_name || r.airline_icao} (${r.airline_icao})`}>
                        <span className="emissions-airline-code">{r.airline_icao}</span>
                        {r.airline_name ? (
                          <span className="emissions-airline-name">{r.airline_name}</span>
                        ) : null}
                      </td>
                      <td>{fmtKg(r.fuel_kg_est)}</td>
                      <td>{fmtKg(r.co2_kg_est)}</td>
                      <td>{fmtKg(r.nox_kg_est, 2)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>

        <section className="emissions-panel">
          <h2>By aircraft type</h2>
          <div className="table-wrap emissions-scroll">
            <table>
              <thead>
                <tr>
                  <th>Type</th>
                  <th>Fuel</th>
                  <th>CO₂</th>
                  <th>NOx</th>
                </tr>
              </thead>
              <tbody>
                {byType.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="muted">
                      No type totals yet.
                    </td>
                  </tr>
                ) : (
                  byType.map((r) => (
                    <tr key={r.aircraft_type}>
                      <td>{r.aircraft_type}</td>
                      <td>{fmtKg(r.fuel_kg_est)}</td>
                      <td>{fmtKg(r.co2_kg_est)}</td>
                      <td>{fmtKg(r.nox_kg_est, 2)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>
      </div>

      <p className="disclaimer">{disclaimer}</p>
    </div>
  );
}
