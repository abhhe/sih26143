# External Data Sources & Ingestion Guide

**Smart India Hackathon 2026 | Problem Statement 26143**  
*Comprehensive documentation of satellite, metocean, and maritime transponder data streams.*

---

## 1. Data Feed Overview

The forensic attribution pipeline integrates five independent data sources:

| Source | Provider | Variables Extracted | Spatial / Temporal Resolution | Access Method / API | License |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Sentinel-1 SAR** | European Space Agency (ESA) Copernicus | VV / VH calibrated backscatter ($\sigma^\circ\text{ dB}$), incidence angles | 10m pixel spacing / 6–12 day repeat orbit | Copernicus Data Space Ecosystem (CDSE) OData / S3 API | Open Access (Creative Commons CC BY-SA 3.0 IGO) |
| **CSIRO Oil Spill Dataset** | CSIRO Australia | Annotated SAR oil slicks & look-alike masks (ships, wakes, low wind) | Patch size $256 \times 256$ / Multi-year archive | Zenodo / CSIRO Data Access Portal | Creative Commons Attribution 4.0 International |
| **ERA5 Atmospheric Reanalysis** | ECMWF / Copernicus Climate Change (C3S) | 10m $u$-component of wind (`u10`), 10m $v$-component of wind (`v10`) | $0.25^\circ \times 0.25^\circ$ ($\sim 28\text{ km}$) / 1-hour intervals | ECMWF CDS API (`cdsapi` Python package) | Copernicus Open License |
| **Global Ocean Physics** | Copernicus Marine Service (CMEMS) | Surface eastward velocity (`uo`), Surface northward velocity (`vo`) | $1/12^\circ$ ($\sim 8\text{ km}$) / Hourly surface field | CMEMS Cop-Marine API (`copernicusmarine` CLI/SDK) | Copernicus Open License |
| **Historical AIS Transponders** | NOAA Marine Cadastre / Coastal Authorities | MMSI, Timestamp, Lat, Lon, SOG, COG, Heading, IMO, Vessel Type | Point pings every 2s–3min per vessel | Marine Cadastre / Terrestrial & Satellite AIS Archival CSV/API | Public Domain (US Gov) / Open Data |

---

## 2. Dataset Ingestion & Preprocessing Pipelines

### 2.1 Sentinel-1 C-Band SAR
- **Instrument:** C-band Synthetic Aperture Radar (5.405 GHz).
- **Acquisition Mode:** Interferometric Wide (IW) swath mode, Level-1 Ground Range Detected (GRD) at High Resolution (HR).
- **Physical Principle:** Capillary and short gravity surface waves (centimeter-scale) cause Bragg resonance backscattering off clean sea water. Mineral oil dampens these ripples due to surface tension anomalies, creating distinct dark patches (specular reflection away from antenna).
- **Preprocessing Pipeline:**
  1. *Orbit File Application:* Precise Orbit Determination (POD) ephemerides update.
  2. *Thermal Noise Removal:* Subtraction of additive instrument thermal noise in cross-polarization channels.
  3. *Radiometric Calibration:* Converting digital numbers ($DN$) to normalized radar cross-section $\sigma^\circ$:
     $$\sigma^\circ_i = \frac{DN_i^2 + A_i}{K_i}$$
     Converted to decibels: $\sigma^\circ_{\text{dB}} = 10 \cdot \log_{10}(\sigma^\circ)$.
  4. *Speckle Filtering:* Refined Lee filter with a $5 \times 5$ moving kernel preserving thin linear slick boundaries while reducing variance in homogeneous sea clutter.

---

### 2.2 ERA5 Wind Vectors
- **Variables:** `10m_u_component_of_wind`, `10m_v_component_of_wind` in meters per second ($\text{m/s}$).
- **Convention:**
  - $u > 0$: Wind blowing towards the East.
  - $v > 0$: Wind blowing towards the North.
  - Meteorological Wind Direction (direction wind is blowing *from*):
    $$\theta_{\text{met}} = (270^\circ - \text{atan2}(v, u) \cdot \frac{180}{\pi}) \pmod{360}$$
- **Interpolation:** 4D bilinear interpolation across spatial coordinates $[x, y]$ and linear interpolation across temporal slices $[t_1, t_2]$.

---

### 2.3 Copernicus Marine Ocean Currents
- **Product:** `GLOBAL_ANALYSISFORECAST_PHY_001_024` (Global Ocean Physics Analysis and Forecast).
- **Variables:** `uo` (eastward sea water velocity at depth $0.5\text{ m}$) and `vo` (northward sea water velocity at depth $0.5\text{ m}$) in $\text{m/s}$.
- **Convention:** Oceanographic vector direction (direction water is traveling *towards*):
  $$\theta_{\text{ocean}} = \text{atan2}(u_o, v_o) \cdot \frac{180}{\pi} \pmod{360}$$
- **Quality Control:** Grid points falling over land or dry-dock bathymetry are assigned `QUALITY_LAND_MASK` and excluded from advection routines.

---

### 2.4 Historical AIS Transponder Ingestion
- **Fields Extracted & Cleaned:**
  - `mmsi` (Maritime Mobile Service Identity, 9-digit integer)
  - `timestamp` (UTC ISO-8601 string)
  - `latitude`, `longitude` (WGS-84 decimal degrees)
  - `speed` (Speed Over Ground, knots)
  - `course` (Course Over Ground, degrees $0–360$)
  - `vessel_type` (Tanker, Cargo, Fishing, Passenger, Tug, Other)
- **Cleaning & Sanity Filters:**
  1. *Coordinate Validation:* Rejection of latitudes outside $[-90, 90]$ and longitudes outside $[-180, 180]$.
  2. *Speed Sanity Filter:* Elimination of impossible GPS teleportation jumps ($SOG > 35\text{ knots}$).
  3. *Timestamp Normalization:* Deduplication and temporal sorting per vessel track.
  4. *Gap Interpolation:* Linear spline dead-reckoning for transmission dropouts $< 30\text{ minutes}$.

---

## 3. Configuration & Environment Variables

All external adapter endpoints, access keys, and storage directories are configurable in `.env`:

```bash
# Data Directories
DATA_RAW_DIR=./data/raw
DATA_PROCESSED_DIR=./data/processed
DATA_FIXTURES_DIR=./data/fixtures

# System Execution Mode ("demo" or "real")
APP_MODE=demo

# Copernicus Data Space Ecosystem (Sentinel-1 SAR)
CDSE_API_URL=https://catalogue.dataspace.copernicus.eu/resto/api
CDSE_USERNAME=your_copernicus_user
CDSE_PASSWORD=your_copernicus_secret

# ECMWF Copernicus Climate Data Store (ERA5 Winds)
CDSAPI_URL=https://cds.climate.copernicus.eu/api/v2
CDSAPI_KEY=your_cds_api_key

# Copernicus Marine Service (CMEMS Ocean Currents)
CMEMS_USERNAME=your_cmems_username
CMEMS_PASSWORD=your_cmems_password

# AIS Data Provider
AIS_PROVIDER=marine_cadastre
AIS_STREAM_URL=https://coast.noaa.gov/digitalcoast/data/ais.html
```
