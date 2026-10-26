import { NavLink, Route, Routes } from "react-router-dom";
import Landing from "./pages/Landing";
import FlightsPage from "./pages/FlightsPage";
import RoutesPage from "./pages/RoutesPage";
import SpecsPage from "./pages/SpecsPage";
import EmissionsPage from "./pages/EmissionsPage";
import AnalyticsPage from "./pages/AnalyticsPage";

export default function App() {
  return (
    <div className="shell">
      <header className="topnav">
        <NavLink to="/" className="brand">
          TrackingPlanesEvent
        </NavLink>
        <nav className="nav-links">
          <NavLink to="/flights" className={({ isActive }) => (isActive ? "active" : "")}>
            Flights
          </NavLink>
          <NavLink to="/emissions" className={({ isActive }) => (isActive ? "active" : "")}>
            Emissions
          </NavLink>
          <NavLink to="/analytics" className={({ isActive }) => (isActive ? "active" : "")}>
            Analytics
          </NavLink>
          <NavLink to="/routes" className={({ isActive }) => (isActive ? "active" : "")}>
            Routes
          </NavLink>
          <NavLink to="/specs" className={({ isActive }) => (isActive ? "active" : "")}>
            Specs
          </NavLink>
        </nav>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/flights" element={<FlightsPage />} />
          <Route path="/routes" element={<RoutesPage />} />
          <Route path="/routes/:flightId" element={<RoutesPage />} />
          <Route path="/specs" element={<SpecsPage />} />
          <Route path="/emissions" element={<EmissionsPage />} />
          <Route path="/analytics" element={<AnalyticsPage />} />
        </Routes>
      </main>
    </div>
  );
}
