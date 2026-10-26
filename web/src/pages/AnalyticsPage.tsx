import { useEffect, useState } from "react";
import { fetchAnalytics, fetchMeta, type AnalyticsPayload } from "../api";

function BarList({
  items,
  labelKey,
  valueKey,
  format = (n: number) => n.toLocaleString(),
}: {
  items: Record<string, unknown>[];
  labelKey: string;
  valueKey: string;
  format?: (n: number) => string;
}) {
  const vals = items.map((i) => Number(i[valueKey] ?? 0));
  const max = Math.max(1, ...vals);
  return (
    <ul className="bar-list">
      {items.map((item, idx) => {
        const label = String(item[labelKey] ?? "—");
        const value = Number(item[valueKey] ?? 0);
        const pct = Math.round((value / max) * 100);
        return (
          <li key={`${label}-${idx}`}>
            <div className="bar-meta">
              <span className="bar-label">{label}</span>
              <span className="bar-value">{format(value)}</span>
            </div>
            <div className="bar-track" aria-hidden>
              <div className="bar-fill" style={{ width: `${pct}%` }} />
            </div>
          </li>
        );
      })}
    </ul>
  );
}

export default function AnalyticsPage() {
  const [data, setData] = useState<AnalyticsPayload | null>(null);
  const [metaNote, setMetaNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchAnalytics()
      .then(setData)
      .catch((e: Error) => setError(e.message));
    fetchMeta().then((m) => {
      const parts = [m.disclaimer, m.generated_at ? `Snapshot: ${m.generated_at}` : null].filter(
        Boolean
      );
      if (parts.length) setMetaNote(parts.join(" · "));
    });
  }, []);

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
              <span>Flights (known type)</span>
            </div>
            <div className="stat">
              <strong>{totals?.flights_estimated ?? 0}</strong>
              <span>With estimates</span>
            </div>
            <div className="stat">
              <strong>
                {totals?.co2_kg_est != null
                  ? Math.round(totals.co2_kg_est).toLocaleString()
                  : "—"}
              </strong>
              <span>CO₂ kg (est.)</span>
            </div>
            <div className="stat">
              <strong>
                {totals?.fuel_kg_est != null
                  ? Math.round(totals.fuel_kg_est).toLocaleString()
                  : "—"}
              </strong>
              <span>Fuel kg (est.)</span>
            </div>
          </div>

          <div className="analytics-grid">
            <section className="analytics-block">
              <h2>Flights by airline</h2>
              <BarList
                items={data.by_airline_flights as Record<string, unknown>[]}
                labelKey="airline_name"
                valueKey="flights"
              />
            </section>
            <section className="analytics-block">
              <h2>Flights by aircraft type</h2>
              <BarList
                items={data.by_type_flights as Record<string, unknown>[]}
                labelKey="aircraft_type"
                valueKey="flights"
              />
            </section>
            <section className="analytics-block">
              <h2>Manufacturer family</h2>
              <BarList
                items={data.by_family as Record<string, unknown>[]}
                labelKey="manufacturer_family"
                valueKey="flights"
              />
            </section>
            <section className="analytics-block">
              <h2>CO₂ by airline</h2>
              <BarList
                items={data.co2_by_airline as Record<string, unknown>[]}
                labelKey="airline_name"
                valueKey="co2_kg_est"
                format={(n) => Math.round(n).toLocaleString()}
              />
            </section>
            <section className="analytics-block">
              <h2>CO₂ by aircraft type</h2>
              <BarList
                items={data.co2_by_type as Record<string, unknown>[]}
                labelKey="aircraft_type"
                valueKey="co2_kg_est"
                format={(n) => Math.round(n).toLocaleString()}
              />
            </section>
          </div>

          <section className="analytics-block analytics-block-wide">
            <h2>Airlines &amp; aircraft types</h2>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Airline</th>
                    <th>Family</th>
                    <th>Type</th>
                    <th>Model</th>
                    <th>Flights</th>
                  </tr>
                </thead>
                <tbody>
                  {data.by_airline_fleet.map((r, i) => (
                    <tr key={`${r.airline_icao}-${r.aircraft_type}-${i}`}>
                      <td>
                        {r.airline_name || r.airline_icao}{" "}
                        <span className="muted">({r.airline_icao})</span>
                      </td>
                      <td>{r.manufacturer_family || "—"}</td>
                      <td>{r.aircraft_type}</td>
                      <td>{r.model_name || "—"}</td>
                      <td>{r.flights}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
          <p className="disclaimer">{data.disclaimer}</p>
        </>
      )}
    </div>
  );
}
