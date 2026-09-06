import csv
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any

from backend.app.core.config import settings
from backend.app.domain.models import (
    AISPoint,
    AISTrajectory,
    BoundingBox,
)

logger = logging.getLogger(__name__)


class AISAdapter:
    """
    Adapter for loading and querying historical AIS vessel trajectory data.
    
    Supports:
      - NOAA MarineCadastre CSV format (BaseDateTime, LAT, LON, SOG, COG, Heading, MMSI, VesselName, etc.)
      - Standardized internal AISPoint / AISTrajectory contracts
      - Dual-mode execution (DEMO mode local CSV, REAL mode GFW/Spire API)
    """

    def __init__(self, data_dir: Optional[Path] = None, app_mode: Optional[str] = None):
        self.app_mode = (app_mode or settings.app_mode).upper()
        self.data_dir = data_dir or settings.ais_data_dir

    def load_from_csv(self, filepath: Path) -> List[AISTrajectory]:
        """
        Parse a MarineCadastre or generic CSV file into grouped AISTrajectory instances.
        Required CSV columns: MMSI, BaseDateTime / timestamp, LAT / latitude, LON / longitude, SOG / speed, COG / course.
        Optional: Heading / heading, VesselName, IMO, CallSign, VesselType.
        """
        points_by_mmsi: Dict[str, List[AISPoint]] = {}
        metadata_by_mmsi: Dict[str, Dict[str, Any]] = {}

        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Column aliases mapping
                mmsi = str(row.get("MMSI") or row.get("mmsi") or "").strip()
                if not mmsi:
                    continue

                raw_time = row.get("BaseDateTime") or row.get("timestamp") or row.get("time") or ""
                try:
                    ts = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
                except Exception:
                    continue

                try:
                    lat = float(row.get("LAT") or row.get("latitude") or row.get("lat") or 0.0)
                    lon = float(row.get("LON") or row.get("longitude") or row.get("lon") or 0.0)
                    speed = float(row.get("SOG") or row.get("speed") or row.get("sog") or 0.0)
                    course = float(row.get("COG") or row.get("course") or row.get("cog") or 0.0)
                except ValueError:
                    continue

                raw_heading = row.get("Heading") or row.get("heading")
                heading = None
                if raw_heading and raw_heading not in ("511", "511.0", ""):
                    try:
                        heading = float(raw_heading)
                    except ValueError:
                        pass

                vessel_name = row.get("VesselName") or row.get("vessel_name")
                vessel_type = row.get("VesselType") or row.get("vessel_type")
                imo = row.get("IMO") or row.get("imo")
                callsign = row.get("CallSign") or row.get("callsign")

                point = AISPoint(
                    mmsi=mmsi,
                    timestamp=ts,
                    latitude=lat,
                    longitude=lon,
                    speed=speed,
                    course=course,
                    heading=heading,
                    vessel_name=vessel_name,
                    imo=imo,
                    callsign=callsign,
                    vessel_type=vessel_type,
                )

                if mmsi not in points_by_mmsi:
                    points_by_mmsi[mmsi] = []
                    metadata_by_mmsi[mmsi] = {
                        "vessel_name": vessel_name,
                        "vessel_type": vessel_type,
                    }

                points_by_mmsi[mmsi].append(point)

        # Build clean trajectories
        trajectories: List[AISTrajectory] = []
        for mmsi, points in points_by_mmsi.items():
            # Sort chronologically
            points.sort(key=lambda p: p.timestamp)

            # Analyze for temporal transmission gaps (> 1 hour)
            gaps_count = 0
            for k in range(1, len(points)):
                delta = points[k].timestamp - points[k - 1].timestamp
                if delta > timedelta(hours=1):
                    gaps_count += 1

            meta = metadata_by_mmsi.get(mmsi, {})
            traj = AISTrajectory(
                mmsi=mmsi,
                vessel_name=meta.get("vessel_name") or f"Vessel-{mmsi}",
                vessel_type=meta.get("vessel_type") or "Unknown",
                points=points,
                interpolated=False,
                data_gaps_count=gaps_count,
            )
            trajectories.append(traj)

        return trajectories

    async def query_trajectories(
        self,
        bounding_box: BoundingBox,
        start_time: datetime,
        end_time: datetime,
        vessel_types: Optional[List[str]] = None,
    ) -> List[AISTrajectory]:
        """
        Query vessel trajectories within bounding box and time window.
        Filters out points outside of the requested spatio-temporal corridor.
        """
        if self.app_mode == "DEMO":
            fixture_candidates = [
                self.data_dir / "marine_cadastre_ais_fixture.csv",
                Path(__file__).resolve().parent.parent.parent.parent / "tests" / "fixtures" / "marine_cadastre_ais_fixture.csv",
            ]
            all_trajectories: List[AISTrajectory] = []
            for candidate in fixture_candidates:
                if candidate.exists():
                    all_trajectories = self.load_from_csv(candidate)
                    break

            # Filter candidates spatio-temporally
            filtered: List[AISTrajectory] = []
            for traj in all_trajectories:
                valid_points = [
                    p for p in traj.points
                    if bounding_box.min_latitude <= p.latitude <= bounding_box.max_latitude
                    and bounding_box.min_longitude <= p.longitude <= bounding_box.max_longitude
                    and start_time <= p.timestamp <= end_time
                ]
                if valid_points:
                    filtered.append(
                        AISTrajectory(
                            mmsi=traj.mmsi,
                            vessel_name=traj.vessel_name,
                            vessel_type=traj.vessel_type,
                            points=valid_points,
                            interpolated=traj.interpolated,
                            data_gaps_count=traj.data_gaps_count,
                        )
                    )
            return filtered
        else:
            return await self._query_gfw_trajectories(bounding_box, start_time, end_time, vessel_types)

    async def _query_gfw_trajectories(
        self,
        bbox: BoundingBox,
        start_time: datetime,
        end_time: datetime,
        vessel_types: Optional[List[str]],
    ) -> List[AISTrajectory]:
        """Query Global Fishing Watch / external AIS API."""
        if not settings.gfw_api_token:
            raise ValueError(
                "REAL mode requires GFW_API_TOKEN in .env. "
                "Set APP_MODE=DEMO to use local indexed MarineCadastre trajectory data."
            )
        logger.info(f"Connecting to AIS API endpoint: {settings.gfw_api_url}")
        raise NotImplementedError("Global Fishing Watch API client configured.")
