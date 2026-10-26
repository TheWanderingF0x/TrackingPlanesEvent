# Emissions estimates (ICEC-inspired)

Portfolio estimates of **fuel**, **CO₂**, and **NOx** per flight.  
**Not** a certified ICAO ICEC or CORSIA calculator.

## Method (v2)

Inspired by [ICAO Carbon Emissions Calculator](https://www.icao.int/environmental-protection/Carbonoffset/Pages/default.aspx) passenger methodology (see local PDF `ICEC_Methodology_Passagers_v13_Final.pdf`):

| Step | Implementation |
|------|----------------|
| Trip distance | **Haversine** (sphere R=6371 km) airport→airport when dep≠arr; else first/last track points; also **speed×duration** candidate; + **ICEC GCD correction**; take **max** with ADS-B path distance. Short OpenSky slices still yield small distances until a fuller day is collected. |
| Aircraft fuel | Cruise burn from `aircraft_specs` × **climb / cruise / descent / LTO** hours from track altitude profile |
| Load factors | Distance-band averages (≈ Intra-Europe style short-haul 82% / 96% pax-to-cargo) |
| Passenger fuel | `total_fuel × pax_to_cargo_factor` |
| CO₂ | `passenger_fuel_kg × 3.16` (ICEC constant) |
| NOx | `total_fuel × nox_index / 1000` from specs |
| Weather | Open-Meteo at **dep / mid / arr**; **headwind** component — model features only (not shown in UI) |
| ML | `scikit-learn` GradientBoosting trained on the proxy labels above |

## Run

```bash
python scripts/run_emissions.py            # with Open-Meteo
python scripts/run_emissions.py --no-weather
python scripts/generate_sample_results.py  # demo gold + weather
```

## Honesty

- No airline fuel uplift / TOW / real pax counts.
- Phase splits are heuristics from ADS-B altitudes.
- Do not present results as regulatory emissions.
