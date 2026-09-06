"""
Custom and Uniform Metocean Provider for Environmental Forcing Overrides and Sensitivity Testing.

Complies with IMeteoOceanProvider interface.
Uses vector_math.py for exact physical conventions:
  - Wind direction: Direction FROM which the wind blows (meteorological)
  - Current direction: Direction TOWARDS which water sets (oceanographic)
"""

from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
import math

from backend.app.domain.models import (
    EnvironmentalState,
    EnvironmentalGridSnapshot,
    BoundingBox,
    CoordinatePoint,
)
from backend.app.adapters.metocean.vector_math import (
    wind_speed_dir_to_uv,
    uv_to_wind_speed_dir,
    current_speed_dir_to_uv,
    uv_to_current_speed_dir,
)


class UniformMeteoOceanProvider:
    """
    Meteo-ocean provider delivering uniform or user-specified wind and current vectors.
    Useful for:
      - Sensitivity testing (same spill with different wind/current scenarios)
      - User overrides from dashboard / API
      - Offshore areas where localized station data or user in-situ observations apply
    """

    def __init__(
        self,
        wind_u: Optional[float] = None,
        wind_v: Optional[float] = None,
        current_u: Optional[float] = None,
        current_v: Optional[float] = None,
        wind_speed_ms: Optional[float] = None,
        wind_direction_deg: Optional[float] = None,
        current_speed_ms: Optional[float] = None,
        current_direction_deg: Optional[float] = None,
        source_label: str = "User Overrides / Analytic Forcing",
    ):
        # Resolve wind vector
        if wind_u is not None and wind_v is not None:
            self.wind_u = float(wind_u)
            self.wind_v = float(wind_v)
        elif wind_speed_ms is not None and wind_direction_deg is not None:
            self.wind_u, self.wind_v = wind_speed_dir_to_uv(wind_speed_ms, wind_direction_deg)
        else:
            # Default mild breeze from West (270 deg, 5.0 m/s -> u=5.0, v=0.0)
            self.wind_u = 5.0
            self.wind_v = 0.0

        # Resolve current vector
        if current_u is not None and current_v is not None:
            self.current_u = float(current_u)
            self.current_v = float(current_v)
        elif current_speed_ms is not None and current_direction_deg is not None:
            self.current_u, self.current_v = current_speed_dir_to_uv(current_speed_ms, current_direction_deg)
        else:
            # Default mild tidal current to North-East (45 deg, 0.25 m/s)
            self.current_u, self.current_v = current_speed_dir_to_uv(0.25, 45.0)

        self.source_label = source_label

    async def get_environmental_state(
        self, latitude: float, longitude: float, timestamp: datetime
    ) -> EnvironmentalState:
        """Return pointwise environmental state using uniform vectors."""
        ts_utc = timestamp if timestamp.tzinfo is not None else timestamp.replace(tzinfo=timezone.utc)

        return EnvironmentalState(
            timestamp=ts_utc,
            latitude=latitude,
            longitude=longitude,
            location=CoordinatePoint(latitude=latitude, longitude=longitude),
            wind_u=round(self.wind_u, 4),
            wind_v=round(self.wind_v, 4),
            current_u=round(self.current_u, 4),
            current_v=round(self.current_v, 4),
            quality_flags={
                "wind": "USER_CONFIGURED_OVERRIDE",
                "current": "USER_CONFIGURED_OVERRIDE",
                "overall": "VALID",
            },
            source={
                "wind": self.source_label,
                "current": self.source_label,
            },
        )

    async def get_grid_slice(
        self,
        bounding_box: BoundingBox,
        start_time: datetime,
        end_time: datetime,
        step_hours: int = 1,
    ) -> List[EnvironmentalGridSnapshot]:
        """Construct uniform grid slices across bounding box and time range."""
        ts_utc = start_time if start_time.tzinfo is not None else start_time.replace(tzinfo=timezone.utc)
        ts_end = end_time if end_time.tzinfo is not None else end_time.replace(tzinfo=timezone.utc)

        # Generate standard 5x5 grid
        lat_step = (bounding_box.max_latitude - bounding_box.min_latitude) / 4.0 or 0.1
        lon_step = (bounding_box.max_longitude - bounding_box.min_longitude) / 4.0 or 0.1
        lats = [round(bounding_box.min_latitude + i * lat_step, 4) for i in range(5)]
        lons = [round(bounding_box.min_longitude + j * lon_step, 4) for j in range(5)]

        snapshots: List[EnvironmentalGridSnapshot] = []
        curr = ts_utc
        step_delta = timedelta(hours=max(1, step_hours))

        while curr <= ts_end:
            u_wind = [[round(self.wind_u, 4) for _ in lons] for _ in lats]
            v_wind = [[round(self.wind_v, 4) for _ in lons] for _ in lats]
            u_curr = [[round(self.current_u, 4) for _ in lons] for _ in lats]
            v_curr = [[round(self.current_v, 4) for _ in lons] for _ in lats]

            snapshots.append(
                EnvironmentalGridSnapshot(
                    timestamp=curr,
                    lats=lats,
                    lons=lons,
                    wind_u_grid=u_wind,
                    wind_v_grid=v_wind,
                    current_u_grid=u_curr,
                    current_v_grid=v_curr,
                )
            )
            curr += step_delta

        return snapshots
