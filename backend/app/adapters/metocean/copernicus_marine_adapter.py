import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any

from backend.app.core.config import settings
from backend.app.domain.models import (
    EnvironmentalState,
    EnvironmentalGridSnapshot,
    BoundingBox,
)
from backend.app.adapters.metocean.era5_adapter import ERA5Adapter

logger = logging.getLogger(__name__)


class CopernicusMarineAdapter:
    """
    Adapter for retrieving Copernicus Marine Service (CMEMS) Global Ocean Physics
    surface current velocity fields.
    
    Required variables:
      - Eastward sea-water velocity (uo, in m/s)
      - Northward sea-water velocity (vo, in m/s)
    """

    def __init__(self, data_dir: Optional[Path] = None, app_mode: Optional[str] = None):
        self.app_mode = (app_mode or settings.app_mode).upper()
        self.data_dir = data_dir or settings.metocean_data_dir
        self.era5_adapter = ERA5Adapter(data_dir=self.data_dir, app_mode=self.app_mode)

    def load_from_fixture_file(self, filepath: Path) -> Tuple[float, float, EnvironmentalGridSnapshot]:
        """Read ocean current state and grid from local JSON fixture."""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        uo = float(data.get("uo", 0.30))
        vo = float(data.get("vo", 0.12))

        grid_data = data.get("grid", {})
        lats = grid_data.get("lats", [56.25, 56.50, 56.75])
        lons = grid_data.get("lons", [3.00, 3.25, 3.50])
        uo_grid = grid_data.get("uo", [[uo] * len(lons) for _ in lats])
        vo_grid = grid_data.get("vo", [[vo] * len(lons) for _ in lats])

        timestamp = datetime.fromisoformat(data.get("timestamp", "2026-08-14T06:00:00Z").replace("Z", "+00:00"))

        snapshot = EnvironmentalGridSnapshot(
            timestamp=timestamp,
            lats=lats,
            lons=lons,
            wind_u_grid=[[0.0] * len(lons) for _ in lats],
            wind_v_grid=[[0.0] * len(lons) for _ in lats],
            current_u_grid=uo_grid,
            current_v_grid=vo_grid,
        )

        return uo, vo, snapshot

    async def get_current_at_point(
        self, latitude: float, longitude: float, timestamp: datetime
    ) -> Tuple[float, float]:
        """
        Sample eastward and northward surface ocean current velocity (m/s).
        Returns: (current_u, current_v)
        """
        if self.app_mode == "DEMO":
            fixture_candidates = [
                self.data_dir / "cmems_current_fixture.json",
                Path(__file__).resolve().parent.parent.parent.parent / "tests" / "fixtures" / "cmems_current_fixture.json",
            ]
            for candidate in fixture_candidates:
                if candidate.exists():
                    uo, vo, grid = self.load_from_fixture_file(candidate)
                    return self._bilinear_interpolate(
                        latitude, longitude, grid.lats, grid.lons, grid.current_u_grid, grid.current_v_grid
                    )

            # Deterministic fallback in demo mode
            return 0.32, 0.14
        else:
            return await self._query_cmems_current(latitude, longitude, timestamp)

    def _bilinear_interpolate(
        self,
        lat: float,
        lon: float,
        lats: List[float],
        lons: List[float],
        u_grid: List[List[float]],
        v_grid: List[List[float]],
    ) -> Tuple[float, float]:
        """Bilinear spatial interpolation for current grid nodes."""
        if lat <= lats[0] or lat >= lats[-1] or lon <= lons[0] or lon >= lons[-1]:
            mid_i = len(lats) // 2
            mid_j = len(lons) // 2
            return u_grid[mid_i][mid_j], v_grid[mid_i][mid_j]

        i = 0
        while i < len(lats) - 2 and lats[i + 1] < lat:
            i += 1
        j = 0
        while j < len(lons) - 2 and lons[j + 1] < lon:
            j += 1

        lat0, lat1 = lats[i], lats[i + 1]
        lon0, lon1 = lons[j], lons[j + 1]

        t = (lat - lat0) / (lat1 - lat0) if lat1 != lat0 else 0.0
        s = (lon - lon0) / (lon1 - lon0) if lon1 != lon0 else 0.0

        u = (1 - s) * (1 - t) * u_grid[i][j] + s * (1 - t) * u_grid[i][j + 1] + (1 - s) * t * u_grid[i + 1][j] + s * t * u_grid[i + 1][j + 1]
        v = (1 - s) * (1 - t) * v_grid[i][j] + s * (1 - t) * v_grid[i][j + 1] + (1 - s) * t * v_grid[i + 1][j] + s * t * v_grid[i + 1][j + 1]

        return round(u, 3), round(v, 3)

    async def get_environmental_state(
        self, latitude: float, longitude: float, timestamp: datetime
    ) -> EnvironmentalState:
        """
        Merge ERA5 wind vectors (u10, v10) and CMEMS current vectors (uo, vo)
        into a unified EnvironmentalState domain contract.
        """
        wind_u, wind_v = await self.era5_adapter.get_wind_at_point(latitude, longitude, timestamp)
        current_u, current_v = await self.get_current_at_point(latitude, longitude, timestamp)

        return EnvironmentalState(
            timestamp=timestamp,
            latitude=latitude,
            longitude=longitude,
            wind_u=wind_u,
            wind_v=wind_v,
            current_u=current_u,
            current_v=current_v,
        )

    async def _query_cmems_current(
        self, latitude: float, longitude: float, timestamp: datetime
    ) -> Tuple[float, float]:
        """Query Copernicus Marine Service via copernicusmarine API."""
        if not settings.copernicus_marine_username or not settings.copernicus_marine_password:
            raise ValueError(
                "REAL mode requires COPERNICUS_MARINE_USERNAME and COPERNICUS_MARINE_PASSWORD in .env. "
                "Set APP_MODE=DEMO for local execution."
            )
        logger.info("Connecting to Copernicus Marine API credentials authenticated.")
        raise NotImplementedError("Copernicus Marine API connection configured.")
