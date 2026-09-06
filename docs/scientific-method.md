# Scientific Methodology & Mathematical Formulations

**Smart India Hackathon 2026 | Problem Statement 26143**  
*Mathematical foundations of spaceborne SAR detection, Lagrangian drift hindcasting, and explainable multi-factor attribution.*

---

## 1. Spaceborne SAR Oil-Slick Segmentation

SAR radar imaging relies on Bragg scattering off ocean capillary ripples. Mineral oil slicks dampen these ripples, decreasing the radar backscatter cross-section ($\sigma^\circ$).

### 1.1 Radiometric Calibration & Speckle Filtering
Raw 16-bit digital numbers ($DN$) from Sentinel-1 Level-1 GRD are converted to normalized radar cross section in decibels ($\sigma^\circ_{\text{dB}}$):
$$\sigma^\circ = \frac{DN^2 + A}{K}, \quad \sigma^\circ_{\text{dB}} = 10 \log_{10}(\sigma^\circ)$$
A **Refined Lee filter** ($5 \times 5$ window) suppresses multiplicative speckle noise while preserving high-gradient linear slick boundaries:
$$\hat{x} = \bar{y} + W \cdot (y - \bar{y}), \quad W = \frac{\text{Var}(x)}{\text{Var}(y)} = \frac{\text{Var}(y) - \bar{y}^2 \sigma_v^2}{\text{Var}(y) (1 + \sigma_v^2)}$$

### 1.2 Dark Slick Segmentation & Look-Alike Rejection
An adaptive Constant False Alarm Rate (CFAR) combined with Otsu bimodal thresholding segments dark pixels:
$$T_{\text{adapt}} = \mu_{\text{sea}} - k \cdot \sigma_{\text{sea}}$$
Potential false alarms are evaluated against look-alike rejection criteria:
- **Low-Wind Areas ($< 3\text{ m/s}$):** Characterized by broad diffuse edges and zero backscatter across large continuous regions.
- **Ship Wakes:** Narrow linear features originating directly from moving AIS-transmitting vessels.
- **Biogenic Slicks:** Low backscatter contrast ($\Delta \sigma^\circ < 2.5\text{ dB}$) with irregular natural meandering patterns.

---

## 2. Lagrangian Particle Drift Kinematics

The physical displacement of slick particles on the ocean surface is governed by the combined action of surface ocean currents, wind leeway drift, and turbulent diffusion.

### 2.1 Governing Kinematic Advection Equation
For particle $p$ at position $\vec{x}_p = [\text{lat}_p, \text{lon}_p]$ and time $t$:
$$\frac{d\vec{x}_p}{dt} = \vec{u}_{\text{current}}(\vec{x}_p, t) + \alpha_{\text{leeway}} \cdot \mathbf{R}(\theta_c) \, \vec{u}_{\text{wind}}(\vec{x}_p, t) + \vec{u}_{\text{diffusion}}$$

Where:
- $\vec{u}_{\text{current}}$: Bilinearly interpolated sea surface velocity vector from CMEMS Global Ocean Physics ($\text{m/s}$).
- $\vec{u}_{\text{wind}}$: 10m atmospheric wind velocity vector from ERA5 reanalysis ($\text{m/s}$).
- $\alpha_{\text{leeway}}$: Empirical wind leeway transfer factor ($3.1\% = 0.031$, standard for medium crude oil).
- $\mathbf{R}(\theta_c)$: Coriolis deflection rotation matrix deflecting wind drift by $\theta_c \approx 12^\circ$ clockwise to the right of wind direction in the Northern Hemisphere:
  $$\mathbf{R}(\theta_c) = \begin{pmatrix} \cos \theta_c & -\sin \theta_c \\ \sin \theta_c & \cos \theta_c \end{pmatrix}$$
- $\vec{u}_{\text{diffusion}}$: Stochastic turbulent diffusion modeled as a Wiener random walk:
  $$\Delta \vec{x}_{\text{diff}} = \vec{\mathcal{N}}(0, 1) \sqrt{2 D \cdot |\Delta t|}$$
  where $D = 2.0\text{ m}^2/\text{s}$ is the horizontal turbulent diffusion coefficient.

### 2.2 2nd-Order Runge-Kutta (RK2) Numerical Integration
To maximize numerical stability over extended hindcasting horizons, advection is solved using midpoint RK2:
$$\vec{k}_1 = \vec{V}(\vec{x}_n, t_n)$$
$$\vec{k}_2 = \vec{V}\left(\vec{x}_n + \frac{\Delta t}{2} \vec{k}_1, \, t_n + \frac{\Delta t}{2}\right)$$
$$\vec{x}_{n+1} = \vec{x}_n + \Delta t \cdot \vec{k}_2$$

- **Backward Hindcasting:** Timestep $\Delta t = -300\text{ s}$ (negative), stepping backwards in time from satellite observation $T_{\text{obs}}$ to release horizon $T_{\text{obs}} - 18\text{ hours}$.
- **Forward Forecasting:** Timestep $\Delta t = +300\text{ s}$ (positive), predicting slick spread forward $T_{\text{obs}} + 12\text{ hours}$.

---

## 3. Source Region & Release Window Reconstruction

At each hindcast timestamp $\tau = T_{\text{obs}} - k \cdot \Delta t$, an ensemble of $N = 100$ particles defines a spatial distribution.

### 3.1 Kernel Density Estimation (KDE)
The 2D spatial probability density function $\hat{f}(x, y)$ of the release origin is reconstructed via bivariate Gaussian KDE:
$$\hat{f}(\vec{x}) = \frac{1}{N \cdot 2\pi h^2} \sum_{i=1}^N \exp\left( -\frac{\|\vec{x} - \vec{x}_i\|^2}{2 h^2} \right)$$
Using Scott's optimal bandwidth rule: $h = N^{-1/6} \cdot \sigma_{\text{ensemble}}$.

From $\hat{f}(\vec{x})$, two iso-probability contour envelopes are computed:
1. **50% Core Credible Zone ($0.59\sigma$):** Region containing the highest particle density corresponding to the most probable spill origin.
2. **90% Extended Uncertainty Envelope ($0.88\sigma$):** Bounding zone capturing $90\%$ of particle dispersion under turbulent spreading and metocean uncertainty.

### 3.2 Release-Time Window
The release window $[T_{\text{earliest}}, T_{\text{latest}}]$ and peak release time $T_{\text{peak}}$ are derived from slick thickness-to-area spreading rates and particle spatial variance minimization:
$$\text{Var}(\tau) = \frac{1}{N} \sum_{i=1}^N \|\vec{x}_i(\tau) - \bar{\vec{x}}(\tau)\|^2$$
$$T_{\text{peak}} = \arg\min_\tau \text{Var}(\tau)$$

---

## 4. Multi-Criteria Attribution Evidence Scoring

To comply with maritime legal frameworks (e.g., UNCLOS Article 217), the system computes an **Attribution Evidence Score** ($0 - 100$), explicitly defined as a multi-criteria forensic index rather than an uncalibrated probability:

$$\text{Score} = w_{\text{sp}} S_{\text{sp}} + w_{\text{tm}} S_{\text{tm}} + w_{\text{tr}} S_{\text{tr}} + w_{\text{dr}} S_{\text{dr}} + w_{\text{bh}} S_{\text{bh}}$$

Initial calibrated weights:
$$\{w_{\text{sp}}: 25, \, w_{\text{tm}}: 20, \, w_{\text{tr}}: 25, \, w_{\text{dr}}: 20, \, w_{\text{bh}}: 10\} \implies \sum w_i = 100$$

### 4.1 Sub-Score Formulations

1. **Spatial Consistency ($S_{\text{sp}} \in [0, 25]$):**
   Evaluates geodesic distance $d_{\text{CPA}}$ from vessel's closest point of approach to source centroid relative to uncertainty radius $R_{\text{unc}}$:
   $$S_{\text{sp}} = 25 \cdot \exp\left( -\frac{1}{2} \left(\frac{d_{\text{CPA}}}{R_{\text{unc}}}\right)^2 \right)$$
   If $d_{\text{CPA}} \le 1.0\text{ km}$, $S_{\text{sp}} = 25.0$.

2. **Temporal Consistency ($S_{\text{tm}} \in [0, 20]$):**
   Measures time delta between CPA timestamp $t_{\text{CPA}}$ and estimated peak release time $T_{\text{peak}}$:
   $$\Delta t = |t_{\text{CPA}} - T_{\text{peak}}|$$
   $$S_{\text{tm}} = 20 \cdot \max\left(0, \, 1 - \frac{\Delta t}{\Delta T_{\text{window}}}\right)$$

3. **Trajectory Corridor Consistency ($S_{\text{tr}} \in [0, 25]$):**
   Tests whether the vessel track physically intersected the 50% core or 90% KDE source polygon and evaluates dwell time $t_{\text{dwell}}$ inside the corridor:
   $$S_{\text{tr}} = \begin{cases} 25.0 & \text{if trajectory crosses 50\% core polygon} \\ 15.0 & \text{if trajectory crosses 90\% envelope} \\ 25 \cdot \exp(-d_{\text{min}} / 5) & \text{if exterior} \end{cases}$$

4. **Drift Physics Alignment ($S_{\text{dr}} \in [0, 20]$):**
   Measures angular alignment $\Delta \theta$ between vessel heading/course $\theta_{\text{cog}}$ and the major elongation axis of the slick $\theta_{\text{slick}}$:
   $$S_{\text{dr}} = 20 \cdot \cos^2(\Delta \theta)$$

5. **Speed Behavioral Anomaly ($S_{\text{bh}} \in [0, 10]$):**
   Detects speed drops or maneuvers during passage through the source zone indicative of discharge operations:
   $$S_{\text{bh}} = 10 \cdot \frac{\Delta v_{\text{drop}}}{v_{\text{cruise}}}$$

---

## 5. Candidate Classification & Fail-Safe Safe-Guard

| Score Range | Classification | Procedural Action |
| :--- | :--- | :--- |
| **80 – 100** | **Strong Candidate** | Priority inspection notice transmitted to Port State Control (PSC). |
| **60 – 79** | **Moderate Candidate** | Secondary audit; cross-reference bunker delivery notes and tank logs. |
| **40 – 59** | **Weak Candidate** | Routine transit logged; low evidentiary significance. |
| **0 – 39** | **Low Consistency** | Candidate excluded from investigation. |

### 5.1 Safe-Fail Safe-Guard (Presumption of Innocence)
If no candidate vessel scores $\ge 50.0 / 100$, or if AIS coverage in the region exhibits critical unrecoverable dark periods, the system triggers the **Safe-Fail Insufficient Evidence Rule**:
- **System Output:** `INSUFFICIENT EVIDENCE`
- `top_candidate = null`
- Mandatory legal notice: *"No vessel crossed the evidentiary threshold. Automated attribution aborted to prevent wrongful maritime accusation."*
