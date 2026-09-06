import json
import math
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any

from backend.app.core.config import settings
from backend.app.domain.models import (
    EnvironmentalState,
    EnvironmentalGridSnapshot,
    CoordinatePoint,
    BoundingBox,
)
from backend.app.adapters.metocean.era5_adapter import ERA5Adapter
from backend.app.adapters.metocean.copernicus_marine_adapter import CopernicusMarineAdapter

logger = logging.getLogger(__name__)


class EnvironmentalForcingService:
    """
    Environmental Forcing Service for atmospheric wind and ocean currents.
    
    Implements the IMeteoOceanProvider protocol.
    Consumes:
      - Wind: ECMWF ERA5 hourly reanalysis (10m u-wind, v-wind in m/s)
      - Currents: Copernicus Marine (CMEMS) Global Ocean Physics (uo, vo in m/s)
      
    Features:
      - 4D spatio-temporal interpolation (spatial bilinear + temporal linear)
      - Meteorological wind direction (direction FROM which wind blows)
      - Oceanographic current direction (direction TOWARDS which water sets)
      - Explicit quality flags (EXACT_REANALYSIS_NODE, SPATIOTEMPORALLY_INTERPOLATED, etc.)
      - Zero silent zero-filling: missing data explicitly flagged.
    """

    def __init__(
        self,
        data_dir: Optional[Path] = None,
        app_mode: Optional[str] = None,
    ):
        self.app_mode = (app_mode or settings.app_mode).upper()
        self.data_dir = data_dir or settings.metocean_data_dir
        self.era5_adapter = ERA5Adapter(data_dir=self.data_dir, app_mode=self.app_mode)
        self.cmems_adapter = CopernicusMarineAdapter(data_dir=self.data_dir, app_mode=self.app_mode)
        self._timeseries_cache: Optional[Dict[str, Any]] = None

    def _load_timeseries_fixture(self) -> Optional[Dict[str, Any]]:
        """Load multi-snapshot timeseries fixture if available."""
        if self._timeseries_cache is not None:
            return self._timeseries_cache

        candidates = [
            self.data_dir / "metocean_timeseries_fixture.json",
            Path(__file__).resolve().parent.parent.parent.parent / "tests" / "fixtures" / "metocean_timeseries_fixture.json",
        ]
        for c in candidates:
            if c.exists():
                try:
                    with open(c, "r", encoding="utf-8") as f:
                        self._timeseries_cache = json.load(f)
                        return self._timeseries_cache
                except Exception as e:
                    logger.warning(f"Error loading {c}: {e}")
        return None

    def _bilinear_interpolate(
        self,
        lat: float,
        lon: float,
        lats: List[float],
        lons: List[float],
        grid: List[List[float]],
    ) -> Tuple[float, bool]:
        """
        Bilinear spatial interpolation on regular latitude-longitude grid.
        Returns: (interpolated_value, is_exact_node)
        """
        # Exact node match check
        for i, glat in enumerate(lats):
            for j, glon in enumerate(lons):
                if math.isclose(lat, glat, abs_tol=1e-5) and math.isclose(lon, glon, abs_tol=1e-5):
                    return float(grid[i][j]), True

        # Clamp check: if within grid range
        if lat < lats[0] or lat > lats[-1] or lon < lons[0] or lon > lons[-1]:
            # Nearest edge clamping for minor numerical roundoff
            i_clamped = 0 if lat <= lats[0] else len(lats) - 1
            j_clamped = 0 if lon <= lons[0] else len(lons) - 1
            return float(grid[i_clamped][j_clamped]), False

        # Find cell indices
        i = 0
        while i < len(lats) - 2 and lats[i + 1] <= lat:
            i += 1
        j = 0
        while j < len(lons) - 2 and lons[j + 1] <= lon:
            j += 1

        lat0, lat1 = lats[i], lats[i + 1]
        lon0, lon1 = lons[j], lons[j + 1]

        t = (lat - lat0) / (lat1 - lat0) if lat1 != lat0 else 0.0
        s = (lon - lon0) / (lon1 - lon0) if lon1 != lon0 else 0.0

        val = (
            (1.0 - s) * (1.0 - t) * grid[i][j]
            + s * (1.0 - t) * grid[i][j + 1]
            + (1.0 - s) * t * grid[i + 1][j]
            + s * t * grid[i + 1][j + 1]
        )
        return float(val), False

    async def get_environmental_state(
        self, latitude: float, longitude: float, timestamp: datetime
    ) -> EnvironmentalState:
        """
        Retrieve and spatio-temporally interpolate 10m wind and ocean current vectors.
        """
        # Standardize timestamp to UTC
        if timestamp.tzinfo is None:
            ts_utc = timestamp.replace(tzinfo=timezone.utc)
        else:
            ts_utc = timestamp.astimezone(timezone.utc)

        ts_data = self._load_timeseries_fixture()

        if ts_data and "snapshots" in ts_data and len(ts_data["snapshots"]) > 0:
            return self._interpolate_from_timeseries(latitude, longitude, ts_utc, ts_data)

        # Fallback to single-snapshot adapters if timeseries not available
        wind_u, wind_v = await self.era5_adapter.get_wind_at_point(latitude, longitude, ts_utc)
        current_u, current_v = await self.cmems_adapter.get_current_at_point(latitude, longitude, ts_utc)

        return EnvironmentalState(
            timestamp=ts_utc,
            latitude=latitude,
            longitude=longitude,
            wind_u=wind_u,
            wind_v=wind_v,
            current_u=current_u,
            current_v=current_v,
            quality_flags={
                "wind": "SPATIALLY_INTERPOLATED",
                "current": "SPATIALLY_INTERPOLATED",
                "overall": "VALID",
            },
            source={
                "wind": "ERA5 Reanalysis (Single Snapshot)",
                "current": "Copernicus Marine Global Ocean Physics",
            },
        )

    def _interpolate_from_timeseries(
        self,
        latitude: float,
        longitude: float,
        ts_utc: datetime,
        ts_data: Dict[str, Any],
    ) -> EnvironmentalState:
        """Perform 4D spatio-temporal interpolation across timeseries snapshots."""
        spatial = ts_data["spatial_domain"]
        lats = spatial["lats"]
        lons = spatial["lons"]
        snapshots = ts_data["snapshots"]

        # Parse snapshot timestamps
        parsed_snaps = []
        for s in snapshots:
            dt = datetime.fromisoformat(s["timestamp"].replace("Z", "+00:00"))
            parsed_snaps.append((dt, s))

        parsed_snaps.sort(key=lambda x: x[0])

        min_time = parsed_snaps[0][0]
        max_time = parsed_snaps[-1][0]

        # Check spatial and temporal boundaries for quality flagging
        spatial_out = (
            latitude < lats[0] or latitude > lats[-1] or longitude < lons[0] or longitude > lons[-1]
        )
        temporal_out = ts_utc < min_time or ts_utc > max_time

        # Temporal bracketing
        if ts_utc <= min_time:
            snap_a = snap_b = parsed_snaps[0][1]
            weight_b = 0.0
            is_exact_time = math.isclose((ts_utc - min_time).total_seconds(), 0.0, abs_tol=1.0)
        elif ts_utc >= max_time:
            snap_a = snap_b = parsed_snaps[-1][1]
            weight_b = 1.0
            is_exact_time = math.isclose((ts_utc - max_time).total_seconds(), 0.0, abs_tol=1.0)
        else:
            # Find interval [k, k+1]
            k = 0
            while k < len(parsed_snaps) - 2 and parsed_snaps[k + 1][0] <= ts_utc:
                k += 1
            t_a, snap_a = parsed_snaps[k]
            t_b, snap_b = parsed_snaps[k + 1]
            span = (t_b - t_a).total_seconds()
            delta = (ts_utc - t_a).total_seconds()
            weight_b = delta / span if span > 0 else 0.0
            is_exact_time = math.isclose(weight_b, 0.0, abs_tol=1e-5) or math.isclose(weight_b, 1.0, abs_tol=1e-5)

        weight_a = 1.0 - weight_b

        # Spatial interpolation on snapshot A
        u10_a, exact_node_a = self._bilinear_interpolate(latitude, longitude, lats, lons, snap_a["u10"])
        v10_a, _ = self._bilinear_interpolate(latitude, longitude, lats, lons, snap_a["v10"])
        uo_a, _ = self._bilinear_interpolate(latitude, longitude, lats, lons, snap_a["uo"])
        vo_a, _ = self._bilinear_interpolate(latitude, longitude, lats, lons, snap_a["vo"])

        # Spatial interpolation on snapshot B
        u10_b, exact_node_b = self._bilinear_interpolate(latitude, longitude, lats, lons, snap_b["u10"])
        v10_b, _ = self._bilinear_interpolate(latitude, longitude, lats, lons, snap_b["v10"])
        uo_b, _ = self._bilinear_interpolate(latitude, longitude, lats, lons, snap_b["uo"])
        vo_b, _ = self._bilinear_interpolate(latitude, longitude, lats, lons, snap_b["vo"])

        # Final temporal blend
        wind_u = round(float(weight_a * u10_a + weight_b * u10_b), 2)
        wind_v = round(float(weight_a * v10_a + weight_b * v10_b), 2)
        current_u = round(float(weight_a * uo_a + weight_b * uo_b), 3)
        current_v = round(float(weight_a * vo_a + weight_b * vo_b), 3)

        # Determine explicit quality flags
        exact_spatial = exact_node_a and exact_node_b

        if spatial_out:
            q_flag = "SPATIALLY_OUT_OF_BOUNDS"
            overall = "DEGRADED"
        elif temporal_out:
            q_flag = "TEMPORALLY_EXTRAPOLATED"
            overall = "DEGRADED"
        elif exact_spatial and is_exact_time:
            q_flag = "EXACT_REANALYSIS_NODE"
            overall = "OPTIMAL"
        elif exact_spatial:
            q_flag = "TEMPORALLY_INTERPOLATED"
            overall = "HIGH_CONFIDENCE"
        elif is_exact_time:
            q_flag = "SPATIALLY_INTERPOLATED"
            overall = "HIGH_CONFIDENCE"
        else:
            q_flag = "SPATIOTEMPORALLY_INTERPOLATED"
            overall = "VALID"

        return EnvironmentalState(
            timestamp=ts_utc,
            latitude=latitude,
            longitude=longitude,
            location=CoordinatePoint(latitude=latitude, longitude=longitude),
            wind_u=wind_u,
            wind_v=wind_v,
            current_u=current_u,
            current_v=current_v,
            quality_flags={
                "wind": q_flag,
                "current": q_flag,
                "overall": overall,
            },
            source={
                "wind": "ERA5 Hourly Reanalysis (ECMWF)",
                "current": "Copernicus Marine Global Ocean Physics Analysis",
            },
        )

    async def get_grid_slice(
        self,
        bounding_box: BoundingBox,
        start_time: datetime,
        end_time: datetime,
        step_hours: int = 1,
    ) -> List[EnvironmentalGridSnapshot]:
        """
        Extract spatial-temporal grid snapshots for continuous Lagrangian particle integration.
        """
        snapshots = []
        ts_data = self._load_timeseries_fixture()
        if not ts_data or "snapshots" not in ts_data:
            return []

        spatial = ts_data["spatial_domain"]
        lats = spatial["lats"]
        lons = spatial["lons"]

        for s in ts_data["snapshots"]:
            dt = datetime.fromisoformat(s["timestamp"].replace("Z", "+00:00"))
            if start_time <= dt <= end_time:
                snap = EnvironmentalGridSnapshot(
                    timestamp=dt,
                    lats=lats,
                    lons=lons,
                    wind_u_grid=s["u10"],
                    wind_v_grid=s["v10"],
                    current_u_grid=s["uo"],
                    current_v_grid=s["vo"],
                )
                snapshots.append(snap)
        return snapshots
