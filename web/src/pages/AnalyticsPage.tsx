import { useEffect, useMemo, useState } from "react";
import { formatAircraftName } from "../aircraftCatalog";
import { fetchAnalytics, fetchMeta, type AnalyticsPayload } from "../api";
import { formatAirportSide, useAirportLabelMode } from "../airportLabels";

const DONUT_COLORS = ["#1a4a6b", "#c45c26", "#2f6b4f", "#9a6b16", "#5b7c99"];

const BAR_COLORS = [
  "#1a4a6b",
  "#c45c26",
  "#2f6b4f",
  "#9a6b16",
  "#5b7c99",
  "#6b3a5b",
  "#3d6b8a",
  "#a85a2e",
  "#4a7a5c",
  "#7a6b2f",
];

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
  const slice = items.slice(0, 10);
  const max = Math.max(1, ...slice.map((i) => Number(i[valueKey] ?? 0)));
  return (
    <div className="vbar-with-legend" role="img" aria-label="CO2 by airline top 10">
      <div className="vbar-plot">
        {slice.map((item, idx) => {
          const label = String(item[labelKey] ?? "—");
          const value = Number(item[valueKey] ?? 0);
          const pct = Math.max(3, Math.round((value / max) * 100));
          const color = BAR_COLORS[idx % BAR_COLORS.length];
          return (
            <div
              className="vbar-col"
              key={`${label}-${idx}`}
              title={`${label}: ${Math.round(value).toLocaleString()} kg CO₂`}
            >
              <div className="vbar-fill-wrap">
                <div
                  className="vbar-fill"
                  style={{ height: `${pct}%`, background: color }}
                />
              </div>
            </div>
          );
        })}
      </div>
      <ol className="vbar-legend">
        {slice.map((item, idx) => {
          const label = String(item[labelKey] ?? "—");
          const value = Number(item[valueKey] ?? 0);
          return (
            <li key={`${label}-leg-${idx}`}>
              <span
                className="vbar-swatch"
                style={{ background: BAR_COLORS[idx % BAR_COLORS.length] }}
              />
              <span className="vbar-legend-label">{label}</span>
              <span className="vbar-legend-val">
                {Math.round(value).toLocaleString()} kg
              </span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

function DonutChart({
  items,
  centerLabel = "Top",
  centerSub = "",
  valueSuffix = "",
}: {
  items: { label: string; value: number }[];
  centerLabel?: string;
  centerSub?: string;
  valueSuffix?: string;
}) {
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
          {centerLabel}
        </text>
        {centerSub ? (
          <text x="70" y="84" textAnchor="middle" className="donut-center-sub">
            {centerSub}
          </text>
        ) : null}
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
              {Math.round(item.value).toLocaleString()}
              {valueSuffix ? ` ${valueSuffix}` : ""}
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

  const top5Aircraft = useMemo(() => {
    if (!data?.by_type_flights?.length) return [];
    return data.by_type_flights.slice(0, 5).map((r) => ({
      label:
        formatAircraftName(r.aircraft_type, { modelName: r.model_name }) ||
        r.aircraft_type ||
        "—",
      value: Number(r.flights ?? 0),
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
                        <td title={r.aircraft_type || undefined}>
                          {formatAircraftName(r.aircraft_type) || r.aircraft_type || "—"}
                        </td>
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
              <p className="chart-unit">Top 10 · est. CO₂ (kg)</p>
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
                    </tr>
                  </thead>
                  <tbody>
                    {data.by_airline_fleet.map((r, i) => (
                      <tr key={`${r.airline_icao}-${r.aircraft_type}-${i}`}>
                        <td>{r.airline_name || r.airline_icao}</td>
                        <td>{r.manufacturer_family || "—"}</td>
                        <td title={r.aircraft_type || undefined}>
                          {formatAircraftName(r.aircraft_type, {
                            modelName: r.model_name
                              ? `${r.manufacturer_family || ""} ${r.model_name}`.trim()
                              : null,
                            family: r.manufacturer_family,
                          }) || "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            <section className="dash-panel">
              <h2>Top 5 aircraft (flights)</h2>
              {top5Aircraft.length ? (
                <DonutChart
                  items={top5Aircraft}
                  centerLabel="A/C"
                  centerSub="top 5"
                  valueSuffix="flights"
                />
              ) : (
                <p className="muted">No aircraft type counts yet.</p>
              )}
            </section>

            <section className="dash-panel">
              <h2>Fleet mix by manufacturer</h2>
              <div className="table-wrap dash-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Family</th>
                      <th>Aircraft</th>
                      <th>Flights (count)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(data.fleet_mix || []).map((r, i) => (
                      <tr key={`${r.manufacturer_family}-${r.aircraft_type}-${i}`}>
                        <td>{r.manufacturer_family || "—"}</td>
                        <td title={r.aircraft_type || undefined}>
                          {formatAircraftName(r.aircraft_type, {
                            modelName: r.model_name
                              ? `${r.manufacturer_family || ""} ${r.model_name}`.trim()
                              : null,
                            family: r.manufacturer_family,
                          }) || "—"}
                        </td>
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
