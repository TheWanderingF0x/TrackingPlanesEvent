import { useEffect, useState } from "react";
import { fetchSpecs, type Spec } from "../api";

export default function SpecsPage() {
  const [specs, setSpecs] = useState<Spec[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchSpecs(false)
      .then((d) => setSpecs(d.specs))
      .catch((e: Error) => setError(e.message));
  }, []);

  const showMissingCol = specs.some(
    (s) => !s.is_complete && (s.missing_fields?.length ?? 0) > 0
  );

  return (
    <div className="page">
      <h1>Aircraft specs</h1>
      {error && <div className="error">{error}</div>}
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Type</th>
              <th>Family</th>
              <th>Model</th>
              <th>Seats</th>
              <th>Fuel kg/h</th>
              <th>Status</th>
              {showMissingCol && <th>Missing</th>}
            </tr>
          </thead>
          <tbody>
            {specs.map((s) => (
              <tr key={s.typecode}>
                <td>{s.typecode}</td>
                <td>{s.manufacturer_family || s.manufacturer}</td>
                <td>{s.model_name || "—"}</td>
                <td>{s.seats_typical ?? "—"}</td>
                <td>{s.fuel_burn_cruise_kg_per_h ?? "—"}</td>
                <td>
                  {s.is_complete ? (
                    <span className="badge badge-ok">complete</span>
                  ) : (
                    <span className="badge badge-warn">incomplete</span>
                  )}
                </td>
                {showMissingCol && (
                  <td>{(s.missing_fields || []).join(", ") || "—"}</td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
