const DATABRICKS_SHOTS = [
  {
    src: "/media/databricks/dashboard-planes-tracker.png",
    alt: "Databricks Planes Tracker dashboard with CO₂ charts and fleet tables",
    caption: "Databricks dashboard — flights, fleet mix, routes, and CO₂ by airline",
  },
  {
    src: "/media/databricks/table-flights-summary.png",
    alt: "Databricks table of airline, aircraft type, callsign, altitude and speed",
    caption: "Enriched flight rows — airline, aircraft type, altitude and speed",
  },
  {
    src: "/media/databricks/table-flight-tracks.png",
    alt: "Databricks table of flight track fields including ICAO24 and coordinates",
    caption: "Track-level fields — callsign, positions, and flight identifiers",
  },
] as const;

export default function AboutPage() {
  return (
    <div className="page page-about">
      <h1>About</h1>
      <p className="lede">
        Why this project exists, and how open-source data meets Databricks for deeper analysis.
      </p>

      <section className="about-block" aria-labelledby="about-purpose">
        <h2 id="about-purpose">Purpose</h2>
        <p>
          Tracking Planes collects aviation data from open-source sources (such as ADS-B
          tracks and public aircraft references), then models those inputs into estimates of
          fuel consumption and NOx produced per flight. The public site focuses on clear,
          daily snapshots — flights, routes, emissions, and analytics — so anyone can explore
          the same picture without a live feed.
        </p>
        <p>
          In parallel, the same pipeline runs on Databricks for a more detailed and easier
          view of the data: notebooks and Lakehouse tables for exploration, plus dashboards
          for fleet mix, top routes, and CO₂ by airline. That workspace is where deeper
          slicing, validation, and iterative modeling happen alongside this site.
        </p>
      </section>

      <section className="about-block" aria-labelledby="about-databricks">
        <h2 id="about-databricks">Databricks in parallel</h2>
        <p className="about-block-lede">
          Screenshots from the Databricks workspace used for detailed visualization and
          analysis of the same open-source–derived dataset.
        </p>
        <div className="about-shots">
          {DATABRICKS_SHOTS.map((shot) => (
            <figure key={shot.src} className="about-shot">
              <img src={shot.src} alt={shot.alt} loading="lazy" />
              <figcaption>{shot.caption}</figcaption>
            </figure>
          ))}
        </div>
      </section>
    </div>
  );
}
