import { NavLink, Route, Routes, useLocation } from "react-router-dom";
import { AirportLabelProvider, AirportLabelToggle } from "./airportLabels";
import Landing from "./pages/Landing";
import FlightsPage from "./pages/FlightsPage";
import RoutesPage from "./pages/RoutesPage";
import EmissionsPage from "./pages/EmissionsPage";
import AnalyticsPage from "./pages/AnalyticsPage";

function showAirportLabelToggle(pathname: string): boolean {
  return (
    pathname.startsWith("/flights") ||
    pathname.startsWith("/analytics") ||
    pathname.startsWith("/routes")
  );
}

function AppShell() {
  const { pathname } = useLocation();
  return (
    <div className="shell">
      <header className="topnav">
        <NavLink to="/" className="brand">
          Tracking Planes
        </NavLink>
        <div className="topnav-end">
          {showAirportLabelToggle(pathname) ? <AirportLabelToggle /> : null}
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
          </nav>
        </div>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/flights" element={<FlightsPage />} />
          <Route path="/routes" element={<RoutesPage />} />
          <Route path="/routes/:flightId" element={<RoutesPage />} />
          <Route path="/emissions" element={<EmissionsPage />} />
          <Route path="/analytics" element={<AnalyticsPage />} />
        </Routes>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <AirportLabelProvider>
      <AppShell />
    </AirportLabelProvider>
  );
}
