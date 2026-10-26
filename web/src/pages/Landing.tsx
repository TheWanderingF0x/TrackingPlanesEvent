import { Link } from "react-router-dom";

export default function Landing() {
  return (
    <section className="hero" aria-label="TrackingPlanesEvent home">
      <div className="hero-inner">
        <h1>TrackingPlanesEvent</h1>
        <p>
          European airline tracks, aircraft specs, and estimated fuel &amp; NOx —
          results from OpenSky and a Databricks-ready lake.
        </p>
        <div className="cta-row">
          <Link className="btn btn-primary" to="/flights">
            Explore flights
          </Link>
          <Link className="btn btn-ghost" to="/analytics">
            View analytics
          </Link>
        </div>
        <p className="hero-note">Data updates daily (or when redeployed) — not a live feed.</p>
      </div>
    </section>
  );
}
