# Scientific Data Layer: Datasets, Ingestion & Operational Modes
## SIH 2026 — Problem Statement 26143
**"Leveraging satellite imagery to determine Oil spills at sea along with AIS data correlations to identify vessel responsible for the spill."**

---

## 1. Dual-Mode Architecture Overview

The scientific data layer operates in two decoupled modes controlled by `APP_MODE` in `.env`:

```
                           ┌───────────────────────────────┐
                           │      APP_MODE in .env         │
                           └──────────────┬────────────────┘
                                          │
                  ┌───────────────────────┴───────────────────────┐
                  ▼                                               ▼
         ┌──────────────────┐                            ┌──────────────────┐
         │    DEMO MODE     │                            │    REAL MODE     │
         │ (Deterministic)  │                            │ (Authenticated)  │
         └────────┬─────────┘                            └────────┬─────────┘
                  │                                               │
         Loads local benchmark                           Queries live cloud
         slices from `data/`:                            APIs & catalogs:
         • Sentinel-1 SAR fixture                        • Copernicus CDSE OData
         • CSIRO patch annotation                        • ECMWF CDS (ERA5)
         • ERA5 NetCDF/JSON                              • Copernicus Marine CMEMS
         • CMEMS currents NetCDF/JSON                    • Global Fishing Watch /
         • MarineCadastre AIS CSV                          NOAA AIS Stream
```

- **`DEMO` Mode**: Zero external network dependency. Loads curated, peer-reviewed benchmark granules and deterministic test fixtures. Guarantees high-speed presentation and 0% risk of network failure during hackathon jury evaluation.
- **`REAL` Mode**: Uses external credentials configured in `.env` to execute live catalog queries and data downloads. If credentials are missing, adapters fail gracefully with actionable error guidance.

---

## 2. Dataset Specifications & Acquisition Guide

### Dataset 1: Sentinel-1 C-SAR (Satellite Observation)
* **Source**: European Space Agency (ESA) / Copernicus Data Space Ecosystem (CDSE).
* **Portal**: [https://dataspace.copernicus.eu/](https://dataspace.copernicus.eu/)
* **API Endpoint**: `https://catalogue.dataspace.copernicus.eu/odata/v1/Products`
* **Sensor / Mode**: Sentinel-1A / Sentinel-1B C-band SAR, Interferometric Wide (IW) Swath Mode, Ground Range Detected (GRD) at high resolution ($10\text{ m}$ pixel spacing).
* **Polarization Used**: **VV** (primary for ocean capillary wave damping and oil slick contrast) and **VH** (cross-polarization for vessel hard-target detection).
* **License & Attribution**: Copernicus Open Access Policy (free and open access for research and commercial use; cite: *"Contains modified Copernicus Sentinel data [year]"*).
* **How to Download (CLI/Python)**:
  ```bash
  # Using CDSE OData API with curl / python
  curl -X GET "https://catalogue.dataspace.copernicus.eu/odata/v1/Products?\$filter=contains(Name,'S1A_IW_GRDH') and ContentDate/Start gt 2026-08-01T00:00:00.000Z" \
       -H "Authorization: Bearer <ACCESS_TOKEN>"
  ```
* **How it enters the system**: Handled by [Sentinel1Adapter](file:///c:/Users/Racharla%20Abhinavteja/OneDrive/Desktop/sih/backend/app/adapters/sar/sentinel1_adapter.py). Parsed into `SatelliteObservation` domain models in `data/sample_sar/`.

---

### Dataset 2: CSIRO Sentinel-1 SAR Oil Spill Dataset (Model Demo & Benchmark)
* **Source**: Commonwealth Scientific and Industrial Research Organisation (CSIRO), Australia / Australian National University.
* **Portal**: CSIRO Data Access Portal & Zenodo SAR Oil Spill Benchmark Repository.
* **Format**: Image patches (TIFF / PNG) and georeferenced polygon masks in GeoJSON format.
* **Variables & Metadata Used**:
  - `label`: `"oil_spill"` vs `"look_alike"` (e.g. biogenic natural film, low-wind dark zone, internal waves).
  - `polygon_coordinates`: Precise bounding vertices $[lon, lat]$.
  - `area_km2`, `perimeter_km`, `orientation_deg`, `thickness_class`.
* **License & Attribution**: Creative Commons Attribution 4.0 International (CC-BY 4.0).
* **How to Download**:
  ```bash
  # Download benchmark tarball from CSIRO Data Access Portal
  mkdir -p data/sample_sar/csiro
  cd data/sample_sar/csiro
  # Extract labeled patches
  ```
* **How it enters the system**: Handled by [OilSpillDatasetAdapter](file:///c:/Users/Racharla%20Abhinavteja/OneDrive/Desktop/sih/backend/app/adapters/sar/csiro_adapter.py). Generates `SpillDetection` domain models with calculated morphometrics and look-alike risk indicators.

---

### Dataset 3: ERA5 Hourly Reanalysis Wind
* **Source**: European Centre for Medium-Range Weather Forecasts (ECMWF) / Copernicus Climate Change Service (C3S).
* **Portal**: [https://cds.climate.copernicus.eu/](https://cds.climate.copernicus.eu/)
* **Required Variables**:
  - `10m u-component of wind` (`u10`): Eastward component at 10 meters above sea level ($\text{m/s}$).
  - `10m v-component of wind` (`v10`): Northward component at 10 meters above sea level ($\text{m/s}$).
* **Spatial & Temporal Resolution**: $0.25^\circ \times 0.25^\circ$ global regular latitude-longitude grid, hourly time steps.
* **Role in Drift Engine**: Direct surface slick leeway forcing ($\alpha_{\text{wind}} = 3.0\% - 3.5\%$ with Coriolis deflection $\theta \in [0^\circ, 15^\circ]$).
* **License & Attribution**: ECMWF Open Data Licence / Copernicus C3S License.
* **How to Download via `cdsapi`**:
  ```python
  import cdsapi

  c = cdsapi.Client()
  c.retrieve(
      'reanalysis-era5-single-levels',
      {
          'product_type': 'reanalysis',
          'variable': ['10m_u_component_of_wind', '10m_v_component_of_wind'],
          'year': '2026',
          'month': '08',
          'day': ['13', '14'],
          'time': [f'{h:02d}:00' for h in range(24)],
          'area': [58, 1, 54, 5], # North Sea bbox: [North, West, South, East]
          'format': 'netcdf',
      },
      'data/sample_metocean/era5_wind_slice.nc'
  )
  ```
* **How it enters the system**: Handled by [ERA5Adapter](file:///c:/Users/Racharla%20Abhinavteja/OneDrive/Desktop/sih/backend/app/adapters/metocean/era5_adapter.py). Bilinearly interpolated across space and time.

---

### Dataset 4: Copernicus Marine Service (CMEMS) Ocean Currents
* **Source**: Copernicus Marine Environment Monitoring Service (CMEMS).
* **Product**: `GLOBAL_ANALYSISFORECAST_PHY_001_024` (Global Ocean Physics Analysis and Forecast).
* **Portal**: [https://marine.copernicus.eu/](https://marine.copernicus.eu/)
* **Required Variables**:
  - `uo`: Eastward sea-water velocity at surface depth ($\text{m/s}$).
  - `vo`: Northward sea-water velocity at surface depth ($\text{m/s}$).
* **Spatial & Temporal Resolution**: $1/12^\circ$ ($\approx 9\text{ km}$) resolution, hourly or daily mean intervals.
* **Role in Drift Engine**: Primary advection velocity vector $\vec{U}_{\text{current}}$ in the backward Runge-Kutta 2nd order Lagrangian integration.
* **License & Attribution**: Open Marine Data License (Copernicus Marine Service).
* **How to Download via `copernicusmarine` CLI**:
  ```bash
  copernicusmarine subset \
      --dataset-id cmems_mod_glo_phy-cur_anfc_0.083deg_PT1H-m \
      --variables uo vo \
      --start-datetime 2026-08-13T00:00:00 \
      --end-datetime 2026-08-14T12:00:00 \
      --minimum-longitude 1.0 --maximum-longitude 5.0 \
      --minimum-latitude 54.0 --maximum-latitude 58.0 \
      --minimum-depth 0.0 --maximum-depth 1.0 \
      --output-filename data/sample_metocean/cmems_currents.nc
  ```
* **How it enters the system**: Handled by [CopernicusMarineAdapter](file:///c:/Users/Racharla%20Abhinavteja/OneDrive/Desktop/sih/backend/app/adapters/metocean/copernicus_marine_adapter.py). Combined with wind fields into unified `EnvironmentalState` instances.

---

### Dataset 5: Historical AIS Trajectories
* **Sources**:
  1. **NOAA MarineCadastre** (US / Global coastal open data): [https://marinecadastre.gov/ais/](https://marinecadastre.gov/ais/)
  2. **Global Fishing Watch (GFW)** (Global vessel activity API): [https://globalfishingwatch.org/](https://globalfishingwatch.org/)
* **Required Fields**:
  - `MMSI`: 9-digit unique maritime transmitter ID.
  - `timestamp`: UTC ISO-8601 ping transmission time (`BaseDateTime`).
  - `latitude` (`LAT`): Geodetic latitude in decimal degrees.
  - `longitude` (`LON`): Geodetic longitude in decimal degrees.
  - `speed` (`SOG`): Speed Over Ground in knots.
  - `course` (`COG`): Course Over Ground in degrees ($0^\circ - 360^\circ$).
  - `heading`: True heading from onboard gyrocompass when available.
  - Ancillary metadata: `VesselName`, `IMO`, `CallSign`, `VesselType`, `Status`.
* **License & Attribution**:
  - NOAA MarineCadastre: Public Domain (U.S. Government work).
  - Global Fishing Watch: CC-BY 4.0 International.
* **How to Download (NOAA MarineCadastre)**:
  ```bash
  # Download filtered daily CSV archives
  curl -O "https://coast.noaa.gov/htdata/CMSP/AISDataHandler/2024/AIS_2024_08_14.zip"
  unzip AIS_2024_08_14.zip -d data/sample_ais/
  ```
* **How it enters the system**: Handled by [AISAdapter](file:///c:/Users/Racharla%20Abhinavteja/OneDrive/Desktop/sih/backend/app/adapters/ais/ais_adapter.py). Reconstructs chronologically ordered `AISTrajectory` objects and calculates dark-period transmission gap anomalies.

---

## 3. Directory Layout for Data Storage

```
data/
├── sample_sar/
│   ├── S1A_NORTH_SEA_20260814.tiff       # High-resolution SAR raster (VV)
│   ├── sar_granule_fixture.json          # Granule metadata & footprint
│   └── csiro/
│       ├── CSIRO_S1_OIL_0042_VV.tiff     # CSIRO training/demo patch
│       └── csiro_spill_fixture.json      # Bounding box, area, mask annotation
│
├── sample_metocean/
│   ├── era5_wind_slice.nc                # NetCDF ERA5 hourly u10, v10 fields
│   ├── era5_wind_fixture.json            # Deterministic demo grid slice
│   ├── cmems_currents.nc                 # NetCDF CMEMS surface uo, vo currents
│   └── cmems_current_fixture.json        # Deterministic demo current grid
│
└── sample_ais/
    ├── AIS_2026_08_14_Zone31.parquet     # Partitioned MarineCadastre archive
    └── marine_cadastre_ais_fixture.csv   # High-density sample trajectory pings
```

---

## 4. Environment Variables Checklist

Ensure your `.env` contains the following keys (defaults pre-configured for DEMO mode):

```ini
APP_MODE=DEMO
DATA_DIR=data
SAR_DATA_DIR=data/sample_sar
CSIRO_DATA_DIR=data/sample_sar/csiro
METOCEAN_DATA_DIR=data/sample_metocean
AIS_DATA_DIR=data/sample_ais

CDSE_BASE_URL=https://catalogue.dataspace.copernicus.eu/odata/v1
CDSE_TOKEN_URL=https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token
CDSE_USERNAME=
CDSE_PASSWORD=
CDSE_CLIENT_ID=cdse-public

CDS_API_URL=https://cds.climate.copernicus.eu/api
CDS_API_KEY=

COPERNICUS_MARINE_USERNAME=
COPERNICUS_MARINE_PASSWORD=

GFW_API_URL=https://gateway.globalfishingwatch.org/v3
GFW_API_TOKEN=

DEFAULT_EVIDENCE_THRESHOLD=50.0
```
