# Oil Spill Source Attribution Platform

**Smart India Hackathon 2026 | Problem Statement 26143**  
*Leveraging satellite imagery to determine Oil spills at sea along with AIS data correlations to identify vessel responsible for the spill.*

[![Backend Pytest Suite](https://img.shields.io/badge/pytest-53%20passed%20(100%25)-emerald)](file:///tests/)
[![Frontend Build](https://img.shields.io/badge/frontend-Vite%20%2B%20React%2018%20(Passing)-cyan)](file:///frontend/)
[![License](https://img.shields.io/badge/license-MIT-blue)](file:///LICENSE)
[![UNCLOS Compliance](https://img.shields.io/badge/UNCLOS-Article%20217%20Compliant-amber)](file:///docs/assumptions-and-limitations.md)

---

## 1. System Mission & The Scientific Challenge

Detecting an oil slick in synthetic aperture radar (SAR) imagery is only half the battle. In open waters, ocean currents and winds transport the slick over hours, creating a substantial spatial offset between the **observed slick location** at satellite overpass ($T_{\text{obs}}$) and the **true release origin** at discharge time ($T_{\text{release}}$).

Naive approaches searching for ships near the observed slick commit an egregious scientific error: by the time the satellite captures the image, the culprit vessel has traveled tens of nautical miles away.

This platform implements the complete 6-stage end-to-end scientific workflow:
$$\text{SATELLITE} \longrightarrow \text{SPILL} \longrightarrow \text{DRIFT} \longrightarrow \text{SOURCE} \longrightarrow \text{AIS} \longrightarrow \text{ATTRIBUTION}$$

---

## 2. Key Capabilities & Innovations

- **Spaceborne SAR Processing:** Calibrates raw Sentinel-1 Level-1 GRD scenes to normalized radar cross section ($\sigma^\circ\text{ dB}$), applies Refined Lee speckle filtering ($5 \times 5$), segments dark slicks via adaptive CFAR/Otsu thresholding, and characterises geometric moments and look-alike risks.
- **Metocean 4D Interpolation:** Bilinear spatial and linear temporal interpolation of ECMWF ERA5 10m atmospheric winds and Copernicus Marine (CMEMS) Global Ocean Physics surface currents ($0.5\text{ m}$) with explicit quality flags.
- **Lagrangian Particle Drift Engine:** 2nd-order Runge-Kutta (RK2) numerical integrator with negative timestep ($\Delta t = -300\text{ s}$) for backward hindcasting ($T_{\text{obs}} \to T_{\text{release}}$) and forward forecasting ($+12\text{ h}$). Incorporates $3.1\%$ wind leeway, $12^\circ$ Coriolis deflection, and turbulent Wiener random walk diffusion ($D = 2.0\text{ m}^2/\text{s}$).
- **Source Envelope KDE:** Bivariate Gaussian Kernel Density Estimation derives the **50% Core Credible Zone** (highest particle density) and **90% Extended Uncertainty Envelope** along with variance-minimized release-time windows.
- **AIS Spatiotemporal Corridor Reconstruction:** Filters invalid coordinates, clamps impossible GPS jumps ($>30\text{ kn}$), reconstructs continuous trajectories, and computes geodesic Closest Point of Approach (CPA) distances and dwell times.
- **Explainable Attribution Evidence Scoring:** Evaluates candidates across 5 weighted dimensions: Spatial ($25\%$), Temporal ($20\%$), Trajectory ($25\%$), Drift ($20\%$), and Behavioral ($10\%$). Outputs an *Attribution Evidence Score* ($0–100$) with counterfactual reasoning and limitations.
- **Ethical AI & Presumption of Innocence:** When no vessel crosses the $50.0/100$ threshold or AIS coverage is non-convergent, the platform issues an explicit `INSUFFICIENT EVIDENCE` determination rather than forcing a false accusation.
- **Forensic Map & Timeline Scrubber:** Interactive Leaflet map featuring real-time scrubbing across the release-to-forecast horizon, live moving vessel markers, dynamic estimated oil position, CPA geodesic vectors, and floating forensic symbology legend.
- **Judge Demonstration & Scientific Validation Modals:**
  - **12-Step Judge Demonstration Runner:** $\sim 60\text{ s}$ automated walkthrough with specs, findings, dual-scenario switching (North Sea Tanker vs Malacca Safe-Fail), and one-click dashboard application.
  - **Monte Carlo Benchmark Layer:** Tests source localization error ($1.82\text{ km}$ mean), release-time error ($0.38\text{ h}$), and systematic sensitivity matrices under $\pm 20\%$ wind/current variations.

---

## 3. Repository Structure

```
sih/
├── backend/                        # Python 3.14 + FastAPI backend
│   ├── app/
│   │   ├── domain/models.py        # Pydantic v2 domain models & validation contracts
│   │   ├── adapters/
│   │   │   ├── sentinel1/          # SAR scene loader & preprocessor (calibration, Lee filter)
│   │   │   ├── spill_detection/    # CFAR/Otsu detector & geometric characterization
│   │   │   ├── environmental/      # ERA5 wind & CMEMS currents 4D interpolation
│   │   │   ├── drift/              # Lagrangian RK2 advection & KDE source estimator
│   │   │   ├── ais/                # AIS trajectory reconstructor & CPA analyzer
│   │   │   ├── attribution/        # Multi-factor scoring, audit & safe-fail engine
│   │   │   └── validation/         # Synthetic benchmark & perturbation generator
│   │   ├── api/v1/                 # REST endpoints (/satellite, /environmental, /drift, /ais, /attribution, /validation)
│   │   ├── core/config.py          # Settings, environment variables, demo/real modes
│   │   └── main.py                 # FastAPI application factory & CORS setup
│   └── requirements.txt
├── frontend/                       # React 18 + TypeScript + Vite frontend
│   ├── src/
│   │   ├── components/
│   │   │   ├── Header.tsx          # Branding, quick action buttons, scientific chain
│   │   │   ├── MapView.tsx         # Forensic map, timeline scrubber, moving vessels, CPA vectors
│   │   │   ├── InputPanel.tsx      # Coordinates, observation datetime, metocean overrides
│   │   │   ├── SpillCard.tsx       # SAR detection confidence, area, perimeter, orientation
│   │   │   ├── SourceCard.tsx      # Reconstructed source centroid, 50%/90% envelopes, release window
│   │   │   ├── CandidateTable.tsx  # Vessel ranking table with scores and classifications
│   │   │   ├── EvidencePanel.tsx   # Top candidate forensic dossier, breakdown bars, audit bullets
│   │   │   ├── InsufficientEvidenceBanner.tsx # Fail-safe alert banner
│   │   │   ├── JudgeDemoModal.tsx  # 12-Step automated jury demonstration runner
│   │   │   └── ValidationModal.tsx # Monte Carlo benchmark & sensitivity matrix panel
│   │   ├── services/               # Adapters, mock data fixtures, API clients
│   │   ├── types/contracts.ts      # TypeScript interfaces mirroring backend Pydantic models
│   │   ├── index.css               # Comprehensive dark forensic design system
│   │   └── App.tsx                 # Master state coordination
│   ├── package.json
│   └── vite.config.ts
├── tests/                          # 53 Automated Pytest tests (100% passing)
│   ├── test_sentinel1_adapter.py
│   ├── test_spill_detection.py
│   ├── test_era5_adapter.py
│   ├── test_copernicus_marine_adapter.py
│   ├── test_environmental_forcing.py
│   ├── test_drift_engine.py
│   ├── test_ais_adapter.py
│   ├── test_vessel_analyzer.py
│   ├── test_attribution_engine.py
│   ├── test_validation_engine.py
│   └── test_config_modes.py
└── docs/                           # Technical Documentation Suite
    ├── architecture.md             # System design, component decoupling, data flow
    ├── data-sources.md             # Ingestion, APIs, licenses, and preprocessing guides
    ├── scientific-method.md        # Governing equations, kinematics, RK2, KDE, scoring
    ├── assumptions-and-limitations.md # Physical boundaries, AIS caveats, UNCLOS Art. 217
    └── demo-guide.md               # 3-minute jury presentation script and Q&A cheat sheet
```

---

## 4. Quickstart Guide

### Prerequisites
- Python 3.11+ (Tested on Python 3.14)
- Node.js 18+ and npm

### 1. Start the Scientific Backend
```bash
cd backend
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```
API Documentation: `http://localhost:8000/docs`

### 2. Start the Interactive Dashboard
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:5173/` in your browser.

### 3. Run the Automated Test Suite
```bash
python -m pytest -v tests/
```
Result: **53 passed in 1.7s**.

---

## 5. Demonstration Scenarios

1. **Scenario 1: High Evidence Tanker (North Sea)**
   - *Observation:* Sentinel-1 SAR acquisition at $56.78^\circ\text{N}, 3.24^\circ\text{E}$ at 06:14 UTC. Slick area: $14.80\text{ km}^2$.
   - *Hydrodynamics:* ERA5 wind $12.4\text{ kn} @ 245^\circ$, CMEMS current $0.38\text{ m/s} @ 065^\circ$.
   - *Attribution Result:* **MT Nordic Titan** passes through 50% core source zone at 01:42 UTC with CPA of $0.82\text{ km}$. Attribution Evidence Score: **88.5 / 100** (*Strong Candidate*).
2. **Scenario 2: Insufficient Evidence & Ethical Safeguard (Strait of Malacca)**
   - *Observation:* Heavy traffic bottleneck with multiple corridor transits.
   - *Attribution Result:* No vessel scores $\ge 50.0 / 100$. Highest candidate is KM Nusantara at $38.5/100$ due to a $+2.8\text{ hr}$ temporal offset. System triggers `INSUFFICIENT EVIDENCE` safe-fail under UNCLOS Article 217.

---

## 6. Scientific Documentation Suite

For comprehensive technical specifications, refer to the documentation in `docs/`:
- [System Architecture](file:///docs/architecture.md)
- [Data Sources & Ingestion Guide](file:///docs/data-sources.md)
- [Scientific Methodology & Equations](file:///docs/scientific-method.md)
- [Physical Assumptions & Legal Guardrails](file:///docs/assumptions-and-limitations.md)
- [SIH Jury Presentation & Demo Guide](file:///docs/demo-guide.md)

---

## 7. License & Disclaimers

This project is developed for the **Smart India Hackathon 2026** (Problem Statement 26143).  
Licensed under the [MIT License](file:///LICENSE).

> **Scientific & Legal Disclaimer:**  
> The Attribution Evidence Score represents algorithmic and physical correlation between spaceborne SAR observations, hydrodynamic drift modeling, and transponder records. It is designed as an investigative triage tool for maritime law enforcement (Port State Control, Coast Guard) under UNCLOS Article 217 and does not constitute judicial proof of culpability in isolation without chemical fingerprinting and physical tank inspection.
