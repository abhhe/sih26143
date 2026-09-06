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

logger = logging.getLogger(__name__)


class ERA5Adapter:
    """
    Adapter for retrieving ECMWF ERA5 hourly wind reanalysis fields.
    
    Required variables:
      - 10m u-component of wind (u10, eastward in m/s)
      - 10m v-component of wind (v10, northward in m/s)
    """

    def __init__(self, data_dir: Optional[Path] = None, app_mode: Optional[str] = None):
        self.app_mode = (app_mode or settings.app_mode).upper()
        self.data_dir = data_dir or settings.metocean_data_dir

    def load_from_fixture_file(self, filepath: Path) -> Tuple[float, float, EnvironmentalGridSnapshot]:
        """Read wind state and grid from local JSON fixture."""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        u10 = float(data.get("u10", 5.0))
        v10 = float(data.get("v10", 3.0))

        grid_data = data.get("grid", {})
        lats = grid_data.get("lats", [56.25, 56.50, 56.75])
        lons = grid_data.get("lons", [3.00, 3.25, 3.50])
        u_grid = grid_data.get("u10", [[u10] * len(lons) for _ in lats])
        v_grid = grid_data.get("v10", [[v10] * len(lons) for _ in lats])

        timestamp = datetime.fromisoformat(data.get("timestamp", "2026-08-14T06:00:00Z").replace("Z", "+00:00"))

        snapshot = EnvironmentalGridSnapshot(
            timestamp=timestamp,
            lats=lats,
            lons=lons,
            wind_u_grid=u_grid,
            wind_v_grid=v_grid,
            current_u_grid=[[0.0] * len(lons) for _ in lats],
            current_v_grid=[[0.0] * len(lons) for _ in lats],
        )

        return u10, v10, snapshot

    async def get_wind_at_point(
        self, latitude: float, longitude: float, timestamp: datetime
    ) -> Tuple[float, float]:
        """
        Sample 10m u-wind and v-wind components (m/s) at given coordinate and timestamp.
        Returns: (wind_u, wind_v)
        """
        if self.app_mode == "DEMO":
            # Search for local era5 fixture
            fixture_candidates = [
                self.data_dir / "era5_wind_fixture.json",
                Path(__file__).resolve().parent.parent.parent.parent / "tests" / "fixtures" / "era5_wind_fixture.json",
            ]
            for candidate in fixture_candidates:
                if candidate.exists():
                    u10, v10, grid = self.load_from_fixture_file(candidate)
                    # Interpolate from grid if coordinates fall within bounds
                    u_interp, v_interp = self._bilinear_interpolate(
                        latitude, longitude, grid.lats, grid.lons, grid.wind_u_grid, grid.wind_v_grid
                    )
                    return u_interp, v_interp

            # Deterministic default in demo mode
            return 6.2, 4.8
        else:
            return await self._query_cds_wind(latitude, longitude, timestamp)

    def _bilinear_interpolate(
        self,
        lat: float,
        lon: float,
        lats: List[float],
        lons: List[float],
        u_grid: List[List[float]],
        v_grid: List[List[float]],
    ) -> Tuple[float, float]:
        """Simple spatial bilinear interpolation for regular latitude/longitude grids."""
        # Check boundary bounds
        if lat <= lats[0] or lat >= lats[-1] or lon <= lons[0] or lon >= lons[-1]:
            # Return nearest center point if slightly outside grid
            mid_i = len(lats) // 2
            mid_j = len(lons) // 2
            return u_grid[mid_i][mid_j], v_grid[mid_i][mid_j]

        # Find bounding cell
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

        return round(u, 2), round(v, 2)

    async def _query_cds_wind(
        self, latitude: float, longitude: float, timestamp: datetime
    ) -> Tuple[float, float]:
        """Query ECMWF Copernicus Climate Data Store (CDS) API."""
        if not settings.cds_api_key:
            raise ValueError(
                "REAL mode requires CDS_API_KEY in .env. "
                "Set APP_MODE=DEMO to use local ERA5 reanalysis slices."
            )
        logger.info(f"Initiating CDS ERA5 wind request to endpoint: {settings.cds_api_url}")
        raise NotImplementedError("CDS API authenticated client configured.")
