import { useEffect, useMemo, useState } from "react";
import { fetchAnalytics, fetchMeta, type AnalyticsPayload } from "../api";
import { formatAirportSide, useAirportLabelMode } from "../airportLabels";

const DONUT_COLORS = ["#1a4a6b", "#c45c26", "#2f6b4f", "#9a6b16", "#5b7c99"];

function formatUpdated(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZoneName: "short",
  });
}

function VerticalBars({
  items,
  labelKey,
  valueKey,
}: {
  items: Record<string, unknown>[];
  labelKey: string;
  valueKey: string;
}) {
  const max = Math.max(1, ...items.map((i) => Number(i[valueKey] ?? 0)));
  const slice = items.slice(0, 12);
  return (
    <div className="vbar-chart" role="img" aria-label="CO2 by airline">
      {slice.map((item, idx) => {
        const label = String(item[labelKey] ?? "—");
        const value = Number(item[valueKey] ?? 0);
        const pct = Math.max(4, Math.round((value / max) * 100));
        return (
          <div className="vbar-col" key={`${label}-${idx}`} title={`${label}: ${Math.round(value)} kg CO₂`}>
            <div className="vbar-value">{Math.round(value).toLocaleString()}</div>
            <div className="vbar-fill-wrap">
              <div className="vbar-fill" style={{ height: `${pct}%` }} />
            </div>
            <span className="vbar-label">{label}</span>
          </div>
        );
      })}
    </div>
  );
}

function DonutChart({
  items,
  labelKey,
  valueKey,
}: {
  items: { label: string; value: number }[];
  labelKey?: string;
  valueKey?: string;
}) {
  void labelKey;
  void valueKey;
  const total = items.reduce((s, i) => s + i.value, 0) || 1;
  const r = 54;
  const c = 2 * Math.PI * r;
  let offset = 0;
  return (
    <div className="donut-wrap">
      <svg viewBox="0 0 140 140" className="donut-svg" aria-hidden>
        <circle cx="70" cy="70" r={r} fill="none" stroke="rgba(26,74,107,0.12)" strokeWidth="18" />
        {items.map((item, idx) => {
          const len = (item.value / total) * c;
          const el = (
            <circle
              key={item.label}
              cx="70"
              cy="70"
              r={r}
              fill="none"
              stroke={DONUT_COLORS[idx % DONUT_COLORS.length]}
              strokeWidth="18"
              strokeDasharray={`${len} ${c - len}`}
              strokeDashoffset={-offset}
              transform="rotate(-90 70 70)"
            />
          );
          offset += len;
          return el;
        })}
        <text x="70" y="68" textAnchor="middle" className="donut-center-label">
          CO₂
        </text>
        <text x="70" y="84" textAnchor="middle" className="donut-center-sub">
          kg
        </text>
      </svg>
      <ul className="donut-legend">
        {items.map((item, idx) => (
          <li key={item.label}>
            <span
              className="donut-swatch"
              style={{ background: DONUT_COLORS[idx % DONUT_COLORS.length] }}
            />
            <span className="donut-legend-label">{item.label}</span>
            <span className="donut-legend-val">
              {Math.round(item.value).toLocaleString()} kg
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function AnalyticsPage() {
  const { mode: airportMode } = useAirportLabelMode();
  const [data, setData] = useState<AnalyticsPayload | null>(null);
  const [metaNote, setMetaNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchAnalytics()
      .then(setData)
      .catch((e: Error) => setError(e.message));
    fetchMeta().then((m) => {
      const parts = [
        m.generated_at ? `Updated ${formatUpdated(m.generated_at)}` : null,
        m.disclaimer || null,
      ].filter(Boolean);
      if (parts.length) setMetaNote(parts.join(" · "));
    });
  }, []);

  const top5Co2 = useMemo(() => {
    if (!data?.co2_by_airline?.length) return [];
    return data.co2_by_airline.slice(0, 5).map((r) => ({
      label: String(r.airline_name || r.airline_icao || "—"),
      value: Number(r.co2_kg_est ?? 0),
    }));
  }, [data]);

  const totals = data?.totals;

  return (
    <div className="page page-analytics">
      <h1>Analytics</h1>
      {metaNote && <p className="update-note">{metaNote}</p>}
      {error && <div className="error">{error}</div>}
      {!data && !error && <p className="muted">Loading…</p>}
      {data && (
        <>
          <div className="stats">
            <div className="stat">
              <strong>{totals?.flights ?? 0}</strong>
              <span>Flights (count)</span>
            </div>
            <div className="stat">
              <strong>{totals?.flights_estimated ?? 0}</strong>
              <span>Estimated (count)</span>
            </div>
            <div className="stat">
              <strong>
                {totals?.co2_kg_est != null
                  ? Math.round(totals.co2_kg_est).toLocaleString()
                  : "—"}
              </strong>
              <span>CO₂ (kg)</span>
            </div>
            <div className="stat">
              <strong>
                {totals?.fuel_kg_est != null
                  ? Math.round(totals.fuel_kg_est).toLocaleString()
                  : "—"}
              </strong>
              <span>Fuel (kg)</span>
            </div>
          </div>

          <div className="dash-grid">
            <section className="dash-panel">
              <h2>Flight data</h2>
              <div className="table-wrap dash-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Airline</th>
                      <th>Aircraft</th>
                      <th>Callsign</th>
                      <th>Max alt. (m)</th>
                      <th>Max speed (m/s)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(data.flight_rows || []).map((r, i) => (
                      <tr key={`${r.callsign}-${i}`}>
                        <td>{r.airline_name || r.airline_icao || "—"}</td>
                        <td>{r.aircraft_type || "—"}</td>
                        <td>{r.callsign || "—"}</td>
                        <td>
                          {r.max_baro_altitude_m != null
                            ? Number(r.max_baro_altitude_m).toFixed(0)
                            : "—"}
                        </td>
                        <td>
                          {r.max_velocity_ms != null
                            ? Number(r.max_velocity_ms).toFixed(1)
                            : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            <section className="dash-panel">
              <h2>CO₂ by airline (kg)</h2>
              <p className="chart-unit">est. CO₂ (kg)</p>
              <VerticalBars
                items={data.co2_by_airline as Record<string, unknown>[]}
                labelKey="airline_name"
                valueKey="co2_kg_est"
              />
            </section>

            <section className="dash-panel">
              <h2>Aircrafts per airline</h2>
              <div className="table-wrap dash-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Airline</th>
                      <th>Manufacturer</th>
                      <th>Aircraft</th>
                      <th>Model</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.by_airline_fleet.map((r, i) => (
                      <tr key={`${r.airline_icao}-${r.aircraft_type}-${i}`}>
                        <td>{r.airline_name || r.airline_icao}</td>
                        <td>{r.manufacturer_family || "—"}</td>
                        <td>{r.aircraft_type}</td>
                        <td>{r.model_name || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            <section className="dash-panel">
              <h2>Top 5 airlines by CO₂ (kg)</h2>
              {top5Co2.length ? (
                <DonutChart items={top5Co2} />
              ) : (
                <p className="muted">No emissions totals yet.</p>
              )}
            </section>

            <section className="dash-panel">
              <h2>Fleet mix by manufacturer</h2>
              <div className="table-wrap dash-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Family</th>
                      <th>Type</th>
                      <th>Model</th>
                      <th>Flights (count)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(data.fleet_mix || []).map((r, i) => (
                      <tr key={`${r.manufacturer_family}-${r.aircraft_type}-${i}`}>
                        <td>{r.manufacturer_family || "—"}</td>
                        <td>{r.aircraft_type || "—"}</td>
                        <td>{r.model_name || "—"}</td>
                        <td>{r.flights}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            <section className="dash-panel">
              <h2>Routes</h2>
              <div className="table-wrap dash-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>{airportMode === "icao" ? "Route (ICAO)" : "Route"}</th>
                      <th>Flights (count)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(data.top_routes || []).length ? (
                      data.top_routes.map((r, i) => (
                        <tr key={`${r.dep_airport_iata}-${r.arr_airport_iata}-${i}`}>
                          <td className={airportMode === "full" ? "route-cell" : undefined}>
                            {formatAirportSide(
                              {
                                icao: r.dep_airport_icao,
                                iata: r.dep_airport_iata,
                                name: r.dep_airport_name,
                              },
                              airportMode
                            )}
                            {" → "}
                            {formatAirportSide(
                              {
                                icao: r.arr_airport_icao,
                                iata: r.arr_airport_iata,
                                name: r.arr_airport_name,
                              },
                              airportMode
                            )}
                          </td>
                          <td>{r.flights}</td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan={2} className="muted">
                          No OD pairs with different airports in this snapshot.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </section>
          </div>
          <p className="disclaimer">{data.disclaimer}</p>
        </>
      )}
    </div>
  );
}
