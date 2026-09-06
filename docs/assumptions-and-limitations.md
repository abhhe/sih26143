# Physical Assumptions, Limitations & Legal Guardrails

**Smart India Hackathon 2026 | Problem Statement 26143**  
*Explicit scientific boundaries, operational limitations, and international maritime legal compliance.*

---

## 1. Physical Modeling Assumptions

### 1.1 2D Surface Transport vs. 3D Weathering
- **Surface Layer Dominance:** The Lagrangian particle advection engine models two-dimensional transport within the uppermost $0.5\text{ m}$ surface mixed layer.
- **Short-Term Horizon ($< 24\text{ Hours}$):** For slicks observed within 12 to 24 hours of discharge, horizontal advection is the dominant kinematic factor. Chemical weathering processes (evaporation of volatile fractions, photo-oxidation, emulsification/mousse formation, natural biodegradation) and vertical entrainment due to breaking waves are treated as second-order volume loss and are not coupled into the horizontal kinematic advection vector.
- **Leeway Constant ($\alpha_{\text{leeway}} = 0.031$):** Calibrated for medium crude oils. Light condensates or heavy bunker fuel oils (HFO) may exhibit leeway factors ranging from $0.025$ to $0.038$.

### 1.2 Metocean Grid Spatial Resolution
- **Sub-Mesoscale Dynamics:** ERA5 atmospheric winds ($0.25^\circ \approx 28\text{ km}$) and Copernicus Marine ocean currents ($1/12^\circ \approx 8\text{ km}$) accurately capture regional synoptic and mesoscale flows. However, localized near-shore phenomena (rip currents, port breakwater wave reflections, and sub-mesoscale eddies $< 5\text{ km}$) are smoothed by bilinear interpolation.
- **Coastal Bathymetry:** In extremely shallow coastal waters ($< 10\text{ m}$ depth), bottom friction and tidal prism asymmetries may introduce additional drift velocity components not resolved in global models.

---

## 2. AIS Maritime Intelligence Limitations

### 2.1 Intentional Dark Periods & Spoofing
- **AIS Deactivation:** Non-compliant vessels deliberately engaging in illegal bilge water discharge or slop tank washing under cover of darkness may disable their Class-A AIS transponder.
- **System Safeguard:** When an AIS trajectory terminates abruptly or exhibits unexplained data gaps prior to entering the source zone, the system flags the vessel with `dark_period_suspected`, preventing false exoneration.

### 2.2 Vessel Size Mandates (IMO SOLAS)
- International Maritime Organization (IMO) SOLAS regulations mandate AIS for commercial ships $\ge 300$ gross tonnage and all passenger ships. Small artisanal crafts, wooden dhows, and unflagged coastal vessels may not broadcast AIS.

### 2.3 Choke-Point Packet Collisions
- In ultra-high-density maritime bottlenecks (e.g., Strait of Malacca, Dover Strait, Singapore Strait), radio-frequency packet collision can reduce satellite AIS ping reception rates. The system utilizes spline interpolation to bridge short gaps ($< 30\text{ minutes}$).

---

## 3. International Maritime Legal Guardrails (UNCLOS Art. 217)

### 3.1 Evidentiary Triage vs. Definitive Guilt
> [!IMPORTANT]
> **Mandatory Evidentiary Disclaimer:**  
> The **Attribution Evidence Score** produced by this platform is an investigative triage metric. It establishes mathematical and physical correlation between satellite observations, drift physics, and vessel tracks. It does **NOT** constitute standalone proof of culpability in a court of law.

- **UNCLOS Article 217 Compliance:** Under the United Nations Convention on the Law of the Sea (UNCLOS) Article 217 (Enforcement by flag States), coastal and port authorities must verify physical chain-of-custody evidence before levying criminal fines or detaining foreign-flagged vessels.
- **Operational Next Steps:** When a vessel receives a **Strong Candidate** classification ($\ge 80/100$), port state control inspectors are alerted to perform:
  1. *Physical Bilge & Slop Tank Audits:* Inspection of Oil Record Book (Part I & II) entries.
  2. *Oil Water Separator (OWS) 15 ppm Monitor Interrogation:* Audit of electronic discharge logs.
  3. *Chemical Fingerprinting:* Gas chromatography-mass spectrometry (GC-MS) biomarker ratio matching between slick sea samples and suspect vessel fuel/slop tanks.

### 3.2 False-Positive Rejection Guardrail
To uphold the fundamental legal presumption of innocence, the platform enforces **Rule PS-26143-R3**:
- If no vessel achieves an Attribution Evidence Score $\ge 50.0 / 100$, the system outputs:
  $$\text{DETERMINATION} = \textbf{INSUFFICIENT EVIDENCE}$$
- The system explicitly refuses to identify a "most likely" culprit when physical evidence is inconclusive, eliminating judicial confirmation bias.
