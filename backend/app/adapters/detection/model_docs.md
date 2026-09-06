# Satellite SAR Oil-Spill Detection Architecture & Limitations
## Module Specification: `SARSpillDetector`
**SIH 2026 — Problem Statement 26143**

---

## 1. Scientific Principles & Pipeline Architecture

The detection of oil spills in Synthetic Aperture Radar (SAR) imagery relies on the physical phenomenon of **Bragg scattering damping**:
- High-frequency capillary and short gravity ocean waves (wavelengths $\lambda \approx 3 - 5\text{ cm}$ matching C-band radar) create diffuse backscatter.
- Viscous petroleum films increase surface tension and dissipate turbulent energy, suppressing capillary waves.
- This creates smooth sea surface specular reflection away from the radar antenna, producing distinct **dark patches** (negative backscatter contrast $\Delta \sigma_0 \le -3.5\text{ dB}$).

### Implemented Architecture:
1. **Radiometric dB Calibration**:
   $$\sigma_0\text{ (dB)} = 10 \cdot \log_{10}(I_{\text{linear}} + \epsilon)$$
2. **Percentile Normalization**: Robust contrast scaling between the 1st and 99th percentiles to suppress sea-surface glint and radar shadow zeros.
3. **Refined Lee Speckle Filter**:
   $$W = \max\left(0, 1 - \frac{C_{\text{noise}}^2}{C_{\text{local}}^2}\right), \quad \hat{I} = \mu_{\text{local}} + W \cdot (I - \mu_{\text{local}})$$
   where $C_{\text{noise}} = 1 / \sqrt{\text{ENL}}$ ($\text{ENL} \approx 4.4$ for Sentinel-1 IW GRD). This preserves sharp oil/water boundary gradients while smoothing high-frequency speckle clutter.
4. **Adaptive Dark-Patch Segmentation**:
   Compares local backscatter against a windowed background envelope ($31 \times 31$ kernel) with morphological closing ($3 \times 3$) to fill intra-slick pinholes and opening ($2 \times 2$) to eliminate residual speckle spikes.
5. **Connected-Component Analysis & Spatial Moments of Inertia**:
   - Area: $A = N_{\text{pixels}} \cdot (\text{resolution})^2$
   - Centroid: 1st spatial moments $(\mu_{10}/\mu_{00}, \mu_{01}/\mu_{00})$ mapped to geodetic WGS84 $(lat, lon)$.
   - Orientation: 2nd-order central moments of inertia:
     $$\theta = \frac{1}{2} \arctan2(2\mu_{11}, \mu_{20} - \mu_{02})$$
   - Elongation / Aspect Ratio: $E = \sqrt{\lambda_1 / \lambda_2}$ from eigenvalues of the inertia tensor.
   - Complexity / Compactness: $C = P^2 / (4 \pi A)$.

---

## 2. Multi-Feature Look-Alike Rejection Layer

SAR imagery contains numerous natural and anthropogenic **dark look-alikes** that can trigger false alarms. The module implements a multi-parameter decision rule:

| Look-Alike Category | Physical Cause | Morphological & Radiometric Characteristics | Look-Alike Risk | System Classification |
| :--- | :--- | :--- | :---: | :---: |
| **Low-Wind Dark Area** | Wind speed $< 2-3\text{ m/s}$ extinguishes capillary waves across wide ocean zones | Massive area ($> 40\text{ km}^2$), very low complexity ($C < 1.4$), diffuse gradual boundaries | **HIGH** | `low_wind_area` (Rejected / Flagged) |
| **Ship Wake** | Turbulent propeller vortex and aerated water trailing a vessel | High elongation ($E > 14.0$), narrow uniform width, aligned with shipping lanes | **HIGH** | `ship_wake` (Flagged) |
| **Natural Biogenic Film** | Plankton blooms, fish oil, and natural surfactant slicks | Low backscatter drop ($-1$ to $-2\text{ dB}$), intricate whorls, high fractal complexity ($C > 5.5$) | **MEDIUM** | `natural_film` (Caution / Medium Confidence) |
| **Mineral Oil Spill** | Heavy crude / bunker fuel discharge from tankers or rigs | High contrast ($-4$ to $-10\text{ dB}$), distinct trailing edge, moderate elongation ($1.5 \le E \le 12.0$), moderate complexity ($1.2 \le C \le 4.5$) | **LOW** | `likely_oil_spill` (High Confidence) |

---

## 3. Dataset & Model Training Specifications

* **Target Training Dataset**: **CSIRO Sentinel-1 SAR Oil Spill Benchmark Dataset**.
* **Input Data Channels**:
  - Sentinel-1 C-SAR IW GRD Dual-Polarization (**VV** primary for capillary damping, **VH** cross-polarization for vessel detection).
* **Input Patch Size**: $256 \times 256$ or $512 \times 512$ pixels ($10\text{ m}$ pixel spacing $\approx 2.56\text{ km} \times 2.56\text{ km}$ to $5.12\text{ km} \times 5.12\text{ km}$).
* **Pluggable Deep Learning Interface**:
  The module implements the `ISpillDetectionEngine` protocol (`detect_spill(observation) -> SpillDetection`). When PyTorch weights (e.g. U-Net with ResNet-34 / MobileNet backbone) are loaded, the adapter swaps internal inference with zero modification to the downstream backward drift hindcast or API endpoints.

---

## 4. Known Physical SAR Limitations

> [!WARNING]
> SAR oil spill detection is physically constrained by ambient sea state and meteorological conditions:
> 1. **Low Wind Extinction ($U_{10} < 2 - 3\text{ m/s}$)**: The entire sea surface appears dark due to mirror-like specular reflection. Oil slicks lose backscatter contrast against surrounding water, producing false positives.
> 2. **High Wind Dispersal ($U_{10} > 12 - 14\text{ m/s}$)**: Breaking waves and turbulent wind mixing emulsify the surface slick, submerging oil droplets beneath the SAR penetration depth ($\approx \text{few millimeters}$ for C-band).
> 3. **Incidence Angle Decay**: Backscatter $\sigma_0$ decreases naturally across the swath from near range ($20^\circ$) to far range ($45^\circ$). Radiometric normalization must account for local incidence angle.
