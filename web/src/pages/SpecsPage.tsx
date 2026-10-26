import { useEffect, useState } from "react";
import { fetchSpecs, type Spec } from "../api";

/** Prefer direct article when known; otherwise Wikipedia search. */
const TYPECODE_WIKI: Record<string, string> = {
  A318: "Airbus_A318",
  A319: "Airbus_A319",
  A320: "Airbus_A320_family",
  A20N: "Airbus_A320neo_family",
  A321: "Airbus_A321",
  A21N: "Airbus_A320neo_family",
  A332: "Airbus_A330",
  A333: "Airbus_A330",
  A339: "Airbus_A330neo",
  A359: "Airbus_A350",
  A35K: "Airbus_A350",
  A388: "Airbus_A380",
  B737: "Boeing_737",
  B738: "Boeing_737_Next_Generation",
  B739: "Boeing_737_Next_Generation",
  B38M: "Boeing_737_MAX",
  B39M: "Boeing_737_MAX",
  B752: "Boeing_757",
  B763: "Boeing_767",
  B772: "Boeing_777",
  B77W: "Boeing_777",
  B788: "Boeing_787_Dreamliner",
  B789: "Boeing_787_Dreamliner",
  B78X: "Boeing_787_Dreamliner",
  E190: "Embraer_E-Jet_family",
  E195: "Embraer_E-Jet_family",
  BCS3: "Airbus_A220",
  AT76: "ATR_72",
  AT75: "ATR_72",
  CRJ9: "Bombardier_CRJ700_series",
  DH8D: "De_Havilland_Canada_Dash_8",
};

function wikipediaHref(s: Spec): string {
  const code = (s.typecode || "").toUpperCase();
  const slug = TYPECODE_WIKI[code];
  if (slug) return `https://en.wikipedia.org/wiki/${slug}`;
  const q = [s.manufacturer, s.model_name || s.typecode].filter(Boolean).join(" ");
  return `https://en.wikipedia.org/w/index.php?search=${encodeURIComponent(q)}`;
}

export default function SpecsPage() {
  const [specs, setSpecs] = useState<Spec[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchSpecs(false)
      .then((d) => setSpecs(d.specs))
      .catch((e: Error) => setError(e.message));
  }, []);

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
              <th>Wikipedia</th>
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
                  <a
                    className="wiki-link"
                    href={wikipediaHref(s)}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    Open
                  </a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
