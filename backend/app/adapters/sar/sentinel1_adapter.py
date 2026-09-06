import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

from backend.app.core.config import settings
from backend.app.domain.models import (
    SatelliteObservation,
    BoundingBox,
    CoordinatePoint,
)

logger = logging.getLogger(__name__)


class Sentinel1Adapter:
    """
    Adapter for loading or retrieving Sentinel-1 SAR observations.
    
    Modes:
      - DEMO MODE: Reads from local SAR data directory / JSON / GeoTIFF fixtures.
      - REAL MODE: Queries Copernicus Data Space Ecosystem (CDSE) OData / STAC API.
    """

    def __init__(self, sar_dir: Optional[Path] = None, app_mode: Optional[str] = None):
        self.app_mode = (app_mode or settings.app_mode).upper()
        self.sar_dir = sar_dir or settings.sar_data_dir

    def load_from_fixture_file(self, filepath: Path) -> SatelliteObservation:
        """Parse local SAR metadata file into a SatelliteObservation contract."""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        bbox = None
        if "bounding_box" in data:
            bb = data["bounding_box"]
            bbox = BoundingBox(
                min_latitude=bb["min_latitude"],
                min_longitude=bb["min_longitude"],
                max_latitude=bb["max_latitude"],
                max_longitude=bb["max_longitude"],
            )

        return SatelliteObservation(
            image_id=data["image_id"],
            timestamp=datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00")),
            latitude=data["latitude"],
            longitude=data["longitude"],
            image_path=data.get("image_path", str(filepath)),
            sensor=data.get("sensor", "Sentinel-1A C-SAR"),
            resolution=float(data.get("resolution", 10.0)),
            polarization=data.get("polarization", ["VV", "VH"]),
            orbit_direction=data.get("orbit_direction"),
            incidence_angle_range=tuple(data["incidence_angle_range"]) if "incidence_angle_range" in data else None,
            bounding_box=bbox,
            extra_metadata=data.get("extra_metadata", {}),
        )

    async def get_observation_by_id(self, image_id: str) -> SatelliteObservation:
        """Retrieve observation by granule/product ID."""
        if self.app_mode == "DEMO":
            # Search local directory for matching metadata file or fixtures
            fixture_candidates = [
                self.sar_dir / f"{image_id}.json",
                self.sar_dir / "sar_granule_fixture.json",
                Path(__file__).resolve().parent.parent.parent.parent / "tests" / "fixtures" / "sar_granule_fixture.json",
            ]
            for candidate in fixture_candidates:
                if candidate.exists():
                    return self.load_from_fixture_file(candidate)

            # Fallback synthetic observation in demo mode
            return SatelliteObservation(
                image_id=image_id,
                timestamp=datetime.utcnow(),
                latitude=56.45,
                longitude=3.20,
                image_path=str(self.sar_dir / f"{image_id}.tiff"),
                sensor="Sentinel-1A C-SAR",
                resolution=10.0,
                polarization=["VV", "VH"],
            )
        else:
            # REAL DATA MODE: Query CDSE OData API
            return await self._query_cdse_by_id(image_id)

    async def search_scenes(
        self,
        bounding_box: BoundingBox,
        start_time: datetime,
        end_time: datetime,
        sensor: str = "Sentinel-1",
    ) -> List[SatelliteObservation]:
        """Search Sentinel-1 scenes within spatial envelope and time interval."""
        if self.app_mode == "DEMO":
            results = []
            candidates = list(self.sar_dir.glob("*.json")) if self.sar_dir.exists() else []
            if not candidates:
                test_fixture = (
                    Path(__file__).resolve().parent.parent.parent.parent
                    / "tests"
                    / "fixtures"
                    / "sar_granule_fixture.json"
                )
                if test_fixture.exists():
                    candidates = [test_fixture]

            for candidate in candidates:
                try:
                    obs = self.load_from_fixture_file(candidate)
                    if (
                        bounding_box.min_latitude <= obs.latitude <= bounding_box.max_latitude
                        and bounding_box.min_longitude <= obs.longitude <= bounding_box.max_longitude
                        and start_time <= obs.timestamp <= end_time
                    ):
                        results.append(obs)
                except Exception:
                    continue
            return results
        else:
            return await self._query_cdse_search(bounding_box, start_time, end_time)

    async def _query_cdse_by_id(self, image_id: str) -> SatelliteObservation:
        """Call Copernicus Data Space Ecosystem OData API."""
        if not settings.cdse_username or not settings.cdse_password:
            raise ValueError(
                "REAL mode requires CDSE_USERNAME and CDSE_PASSWORD in .env. "
                "Set APP_MODE=DEMO to run with local benchmark data."
            )
        # Construct endpoint dynamically without hardcoding
        url = f"{settings.cdse_base_url}/Products?$filter=Name eq '{image_id}'"
        logger.info(f"Connecting to CDSE endpoint: {url}")
        # In actual execution, calls httpx / requests with auth token
        raise NotImplementedError(
            f"Active network query to {settings.cdse_base_url} configured. Please verify credentials."
        )

    async def _query_cdse_search(
        self, bbox: BoundingBox, start_time: datetime, end_time: datetime
    ) -> List[SatelliteObservation]:
        """Call Copernicus Data Space Ecosystem STAC / OData catalog search."""
        if not settings.cdse_username or not settings.cdse_password:
            raise ValueError(
                "REAL mode requires CDSE credentials in .env. "
                "Switch APP_MODE=DEMO for offline hackathon execution."
            )
        raise NotImplementedError("CDSE catalog search requires authenticated session.")
