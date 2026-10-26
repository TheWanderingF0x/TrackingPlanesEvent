# TrackingPlanesEvent — Project Management Plan

**Goal:** Cloud-ready portfolio product — OpenSky collect → Databricks lakehouse → ML fuel/NOx estimates → modern React results site  
**Priority:** 1 of 3  
**Estimate:** ~30–45 hours across phases B–G (not a 1–2 day polish-only pass)

---

## 1. Objectives

| Objective | Success metric |
|-----------|----------------|
| Enrich flights in lakehouse | Tip aeronavă, nr. zbor, companie, OD + track in silver/gold |
| Specs DB with gaps visible | `aircraft_specs.is_complete` / `missing_fields` filterable |
| Emissions estimates | Fuel + NOx per flight with Open-Meteo weather features |
| Modern results website | React + FastAPI on Oracle; Streamlit = internal only |
| Safe public repo | No secrets in git; SECURITY.md followed |

**Out of scope (v1):** Certified ICAO/CORSIA emissions, Streamlit as public portal, OpenSky polling from Databricks, Terraform/HA, user auth on website.

---

## 2. Locked architecture decisions

| Concern | Choice |
|---------|--------|
| 24/7 collector | Oracle Always Free (`deploy/oracle/`) |
| Lakehouse | Databricks Volume → bronze / silver / gold Delta |
| Weather API | Open-Meteo (free, no key) |
| Public website | Vite + React + TypeScript + FastAPI |
| Internal explorer | Existing Streamlit app |
| ML v1 | scikit-learn fuel + NOx estimates |

```text
OpenSky → Oracle collector → Parquet
                ↓
         Databricks Volume → bronze → silver (OD, type, specs)
                ↓
         Open-Meteo + sklearn → gold.flight_emissions_estimates
                ↓
         FastAPI → React results site (Oracle nginx)
```

---

## 3. Work Breakdown Structure

### Phase A — Baseline (done)
Collector, Spark sessionize, aircraft type join, Streamlit explorer, Oracle package, secret hygiene.

### Phase B — Portfolio polish (2–3 h)
| ID | Task | Est. |
|----|------|------|
| B1 | README architecture + interview bullets | 1 h |
| B2 | Screenshot / hero visual in `docs/images/` | 0.5 h |
| B3 | Secret audit + CHANGELOG bump | 0.5 h |

### Phase D — Cloud runtime (4–6 h)
| ID | Task | Est. |
|----|------|------|
| D1 | Docs: deploy-then-works Oracle + Parquet→Volume sync | 2 h |
| D2 | Databricks notebook skeletons (bronze/silver/gold) | 2 h |
| D3 | nginx path prep for API/static site | 1 h |

### Phase E — Enrichment + specs (8–12 h)
| ID | Task | Est. |
|----|------|------|
| E1 | OD airport inference + manufacturer family | 4 h |
| E2 | `aircraft_specs` reference + completeness flags | 3 h |
| E3 | Pipeline write silver exports for API/Databricks | 2–4 h |

### Phase F — Weather + ML (8–12 h)
| ID | Task | Est. |
|----|------|------|
| F1 | Open-Meteo client (mid-route / OD) | 2 h |
| F2 | Feature table + sklearn fuel/NOx | 4–6 h |
| F3 | Gold Parquet export + Databricks job notes | 2 h |

### Phase G — Modern website (8–12 h)
| ID | Task | Est. |
|----|------|------|
| G1 | FastAPI `/api/flights|routes|specs|emissions` | 3 h |
| G2 | React pages: landing, flights, map, specs, emissions | 5–7 h |
| G3 | Oracle systemd + nginx deploy docs | 2 h |

---

## 4. Data honesty (document in UI)

- **OD airports:** ADS-B nearest-airport estimate (or OpenSky flight API when available) — not official schedules.
- **Incomplete specs:** Marked `is_complete=false`; exclude from analysis until filled.
- **ML emissions:** Portfolio estimates, not regulatory measurements.

---

## 5. Definition of Done

- [ ] PM plan matches shipped architecture
- [ ] Silver flights include type, callsign, airline, OD, track link
- [ ] Specs table with completeness flags
- [ ] Gold emissions estimates with weather features
- [ ] React site serves results-only views
- [ ] SETUP + DATABRICKS docs; CHANGELOG updated
- [ ] `scripts/check_no_secrets.py` clean

---

## 6. Interview talking points

1. Why Oracle for polling vs Databricks for lakehouse/ML  
2. How OD + specs incompleteness are modeled for honest analytics  
3. Physics-inspired fuel/NOx proxies + sklearn correction with free weather features  
4. Why React+FastAPI for the public face vs Streamlit for debug  
