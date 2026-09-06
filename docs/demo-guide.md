# SIH 2026 Jury Presentation & Demonstration Guide

**Smart India Hackathon 2026 | Problem Statement 26143**  
*3-to-5 minute live demonstration walkthrough script for hackathon judges and evaluators.*

---

## 1. Quickstart: Launching the Prototype

### Terminal 1: Backend Server (FastAPI)
```bash
cd backend
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```
*Health Check:* `http://localhost:8000/health`  
*Interactive Swagger API Docs:* `http://localhost:8000/docs`

### Terminal 2: Frontend Dashboard (Vite + React)
```bash
cd frontend
npm install
npm run dev
```
*Open in Browser:* `http://localhost:5173/`

### Running Automated Test Suite
```bash
python -m pytest -v tests/
# Result: 53 passed in ~1.7 seconds
```

---

## 2. Recommended 3-Minute Live Presentation Script

### Minute 1: The Space-to-Vessel Problem & Scientific Chain
> *"Respected Judges, Problem Statement 26143 tackles maritime hit-and-run oil discharges at sea. When satellite radar detects an oil slick, the culprit vessel is already tens of nautical miles away. Most naive approaches simply search for ships near the slick at observation time—which is scientifically invalid because ocean currents and winds have moved the slick over hours.*
>
> *Our platform implements the complete 6-stage scientific workflow:  
> SATELLITE $\rightarrow$ SPILL $\rightarrow$ DRIFT $\rightarrow$ SOURCE $\rightarrow$ AIS $\rightarrow$ ATTRIBUTION.*
>
> *Notice our header breadcrumbs reflecting this exact chain."*

---

### Minute 2: Automated 60-Second Judge Demo & Ethical Safeguard
> *"Let us run our 12-Step Automated Judge Walkthrough by clicking 'Run Demo Investigation' in the header.*
>
> *(Click 'Run Demo Investigation')*
>
> *Watch how the system guides us through every scientific stage:*
> 1. *Sentinel-1 C-SAR ingestion & Lee speckle filtering.*
> 2. *Adaptive CFAR dark slick segmentation and geometric moment calculation.*
> 3. *ERA5 wind and CMEMS ocean current 4D interpolation.*
> 4. *Lagrangian Runge-Kutta 2nd-order backward advection.*
> 5. *KDE source envelope reconstruction: yielding a 50% core credible zone and 90% uncertainty boundary.*
> 6. *Spatiotemporal AIS trajectory reconstruction and Closest Point of Approach (CPA) calculation.*
>
> *(Click Scenario B: Malacca Strait)*
>
> *Notice our Ethical AI Safeguard: In dense transit corridors where evidence is ambiguous, the system triggers 'INSUFFICIENT EVIDENCE' rather than falsely accusing an innocent captain. We enforce the legal presumption of innocence under UNCLOS Article 217.*
>
> *(Switch back to Scenario A, click Step 12 on the ribbon)*
>
> *For our North Sea scenario, the platform compiles this complete forensic dossier identifying MT Nordic Titan with an Attribution Evidence Score of 88.5 / 100."*

---

### Minute 3: Forensic Map & Timeline Scrubber
> *(Click 'Apply & View on Interactive Map')*
>
> *"Now let's inspect the forensic map:*
> - *The bright cyan polygon is the observed SAR spill at 06:14 UTC.*
> - *The dashed amber lines trace 100 backward Lagrangian particles drifting back in time.*
> - *The orange shaded region is the 50% core source zone.*
> - *The dashed magenta trails show the forward forecast +12 hours.*
>
> *(Grab the Timeline Scrubber at the bottom of the map and scrub backwards to T_peak = 01:45 UTC)*
>
> *Watch the vessel markers and the estimated oil position move backwards in time dynamically! At 01:42 UTC, MT Nordic Titan passes directly through the 50% core source envelope with a CPA distance of just 0.82 km!*
>
> *(Click on MT Nordic Titan in the candidate table)*
>
> *The map immediately highlights the vessel's track and renders a dashed CPA geodesic vector directly to the source centroid.*
>
> *(Click 'Validation Benchmarks' in the header)*
>
> *Finally, our Scientific Benchmark Layer proves algorithm stability across 25 Monte Carlo synthetic simulations: achieving a mean source error of 1.82 km and 94.2% Top-1 candidate recovery, validated under ±20% wind and current perturbations."*

---

## 3. High-Impact Judge Q&A Cheat Sheet

| Evaluator Question | Winning Response |
| :--- | :--- |
| **"Why not use a simple Deep Learning black box for the entire pipeline?"** | *"Attribution in international waters has severe legal consequences under UNCLOS Article 217. A black-box neural net cannot be audited in maritime court. We use neural/CFAR segmentation for the satellite mask where vision excels, but rigorous Runge-Kutta hydrodynamic physics and explainable multi-factor scoring for attribution so every metric is mathematically verifiable."* |
| **"What if the vessel turns off its AIS transponder?"** | *"That is a classic maritime tactic ('going dark'). Our system detects sudden transponder dropouts along transit corridors and flags them as `dark_period_suspected`. The vessel is not exonerated; instead, its last known dead-reckoned vector is projected through the source region and tagged for port state scrutiny."* |
| **"Does this work without active internet during the presentation?"** | *"Yes! All five data adapters feature built-in deterministic fixtures (NetCDF, GeoTIFF, and cleaned AIS pings). If external APIs are unavailable or credentials are not supplied, the platform runs offline seamlessly."* |
| **"Why do you call it an 'Attribution Evidence Score' instead of a probability?"** | *"Calling it a probability implies a calibrated Bayesian prior over all global maritime traffic, which would be scientifically dishonest. Calling it an Attribution Evidence Score correctly frames it as a multi-criteria forensic index designed for coast guard inspection triage, strictly adhering to scientific integrity."* |
