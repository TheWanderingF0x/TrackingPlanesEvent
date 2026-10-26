import { Link } from "react-router-dom";

export default function Landing() {
  return (
    <section className="hero" aria-label="Tracking Planes home">
      <div className="hero-inner">
        <h1>Tracking Planes</h1>
        <p>
          European airline tracks, routes on the map, and estimated fuel &amp; NOx —
          from ADS-B data, updated daily on this site.
        </p>
        <div className="cta-row">
          <Link className="btn btn-primary" to="/flights">
            Explore flights
          </Link>
          <Link className="btn btn-ghost" to="/analytics">
            View analytics
          </Link>
        </div>
        <p className="hero-note">Data updates daily — not a live feed.</p>
      </div>
      <p className="hero-credit">
        Photo{" "}
        <a href="https://www.vulpeahoinara.com" target="_blank" rel="noopener noreferrer">
          vulpeahoinara.com
        </a>
      </p>
    </section>
  );
}
