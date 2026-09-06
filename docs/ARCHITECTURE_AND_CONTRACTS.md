# System Architecture & Data Contracts Specification
## SIH 2026 — Problem Statement 26143
**"Leveraging satellite imagery to determine Oil spills at sea along with AIS data correlations to identify vessel responsible for the spill."**

---

## 1. System Overview & Scientific Workflow

The core challenge of PS 26143 is closing the loop between **remote sensing (SAR)**, **metocean physical oceanography (wind & currents)**, **backward trajectory hindcasting**, and **maritime vessel tracking (AIS)** to produce legally defensible, explainable attribution evidence.

### End-to-End Scientific Workflow:
```
[Sentinel-1 SAR Observation]
         │
         ▼
[Oil-Spill Detection & Morphometry Characterization]
  • Segmentation mask, area, perimeter, orientation, confidence
         │
         ▼
[Meteo-Oceanographic Environmental Ingestion]
  • ERA5 10m wind (u, v) + Copernicus Marine currents (u, v)
         │
         ▼
[Lagrangian Backward Drift Hindcasting (Monte Carlo)]
  • Advection by currents + wind leeway factor (3.0-3.5%) + turbulent dispersion
         │
         ▼
[Probable Source Region & Release-Time Window]
  • Spatiotemporal probability envelope / KDE boundary
         │
         ▼
[Historical AIS Trajectory Ingestion & Reconstruction]
  • Spatial/temporal corridor filtering + spline interpolation
         │
         ▼
[Candidate Vessel Multi-Criteria Scoring]
  • Spatial proximity, temporal alignment, track overlap, drift intersection, behavior
         │
         ▼
[Explainable Attribution Evidence Dossier]
  • "Attribution Evidence Score" (NOT uncalibrated probability)
  • Explicit "Insufficient Evidence" support
         │
         ▼
[Interactive Map & Investigation Workbench (React + MapLibre/Leaflet)]
```

---

## 2. Pluggable Architecture & Clean Boundaries

To ensure that real data sources (Copernicus Data Space Ecosystem, ERA5, Copernicus Marine CMEMS, Global Fishing Watch / NOAA MarineCadastre) can be swapped with local files, mock generators, or different cloud APIs without modifying the scientific engine, the system implements a **Hexagonal / Adapter Pattern**:

```
                       ┌─────────────────────────────────────┐
                       │           FastAPI REST API          │
                       │    (/investigations, /pipeline, ...)│
                       └──────────────────┬──────────────────┘
                                          │
                                          ▼
                       ┌─────────────────────────────────────┐
                       │     Core Pipeline Orchestrator      │
                       └──────────────────┬──────────────────┘
                                          │
        ┌─────────────────────────────────┼─────────────────────────────────┐
        │                                 │                                 │
        ▼                                 ▼                                 ▼
┌──────────────┐                  ┌──────────────┐                  ┌──────────────┐
│  ISatellite  │                  │ IMeteoOcean  │                  │     IAIS     │
│   Provider   │                  │   Provider   │                  │   Provider   │
└───────┬──────┘                  └───────┬──────┘                  └───────┬──────┘
        │                                 │                                 │
  ┌─────┴──────────┐               ┌──────┴─────────┐                ┌──────┴─────────┐
  │ - CopernicusAPI│               │ - ERA5 NetCDF  │                │ - MarineCadastre│
  │ - CSIRO Dataset│               │ - CMEMS NetCDF │                │ - GFW API      │
  │ - LocalSARFile │               │ - OpenMeteo    │                │ - CSV Trajectory│
  │ - MockSAR      │               │ - MockMeteo    │                │ - MockAIS      │
  └────────────────┘               └────────────────┘                └────────────────┘
```

---

## 3. Scientific Terminology & Attribution Guidelines

1. **Attribution Evidence Score**:
   - The aggregate score is strictly termed the **"Attribution Evidence Score"** (scaled 0 to 100 or 0.0 to 1.0).
   - Under no circumstances shall this score be referred to as a "probability of guilt" or "true probability" unless calibrated against an empirical statistical ground-truth distribution.
2. **Insufficient Evidence Flag**:
   - If no candidate vessel attains a score exceeding the calibrated investigation threshold (default $E_{\text{threshold}} = 50.0$), the system formally outputs:
     `classification: "Insufficient Evidence"`
   - The report lists all evaluated vessels with explicit explanations for disqualification (e.g., temporal mismatch, distance exceeded $3\sigma$ drift envelope, AIS dark period without corroborating evidence).
3. **Drift Physics Standard**:
   $$\vec{U}_{\text{drift}} = \vec{U}_{\text{current}} + \alpha_{\text{wind}} \cdot \mathbf{R}(\theta) \vec{U}_{\text{wind}} + \vec{U}'_{\text{diff}}$$
   - $\alpha_{\text{wind}} \in [0.030, 0.035]$ (3.0% – 3.5% wind leeway)
   - $\theta$: Coriolis deflection angle ($\approx 0^\circ - 15^\circ$ clockwise in NH)
   - $\vec{U}'_{\text{diff}}$: Brownian/random-walk turbulent diffusion coefficient ($D_h \approx 1 - 10 \, \text{m}^2/\text{s}$).

---
