import csv
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any, Union

from backend.app.core.config import settings
from backend.app.domain.models import (
    AISPoint,
    AISTrajectory,
    BoundingBox,
)

logger = logging.getLogger(__name__)


class AISProvider(ABC):
    """
    Abstract Base Class for AIS data providers.
    Provides historical vessel positions and trajectories for spatio-temporal correlation.
    """

    @abstractmethod
    def get_historical_positions(
        self,
        bounding_box: Optional[BoundingBox] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch historical AIS positions as a list of raw point dictionaries.
        """
        pass


class CSVAISProvider(AISProvider):
    """
    AIS Provider that loads historical records from local CSV files
    (e.g., NOAA MarineCadastre format or standard AIS CSVs).
    """

    def __init__(self, filepath: Union[str, Path]):
        self.filepath = Path(filepath)
        if not self.filepath.exists():
            raise FileNotFoundError(f"AIS CSV dataset file not found: {self.filepath}")

    def get_historical_positions(
        self,
        bounding_box: Optional[BoundingBox] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        raw_pings: List[Dict[str, Any]] = []

        with open(self.filepath, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Column normalization
                mmsi = str(row.get("MMSI") or row.get("mmsi") or "").strip()
                if not mmsi:
                    continue

                raw_time = row.get("BaseDateTime") or row.get("timestamp") or row.get("time") or ""
                try:
                    ts = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                except Exception:
                    continue

                try:
                    lat = float(row.get("LAT") or row.get("latitude") or row.get("lat") or 0.0)
                    lon = float(row.get("LON") or row.get("longitude") or row.get("lon") or 0.0)
                    speed = float(row.get("SOG") or row.get("speed") or row.get("sog") or 0.0)
                    course = float(row.get("COG") or row.get("course") or row.get("cog") or 0.0)
                except (ValueError, TypeError):
                    continue

                # Optional bounding box pre-filter
                if bounding_box:
                    if not (bounding_box.min_latitude <= lat <= bounding_box.max_latitude and
                            bounding_box.min_longitude <= lon <= bounding_box.max_longitude):
                        continue

                # Optional temporal pre-filter
                if start_time and ts < start_time:
                    continue
                if end_time and ts > end_time:
                    continue

                raw_heading = row.get("Heading") or row.get("heading")
                heading = None
                if raw_heading not in (None, "", "511", "511.0", 511):
                    try:
                        h = float(raw_heading)
                        if 0.0 <= h < 360.0:
                            heading = h
                    except ValueError:
                        pass

                raw_pings.append({
                    "mmsi": mmsi,
                    "timestamp": ts.isoformat(),
                    "latitude": lat,
                    "longitude": lon,
                    "speed": speed,
                    "course": course,
                    "heading": heading,
                    "vessel_name": row.get("VesselName") or row.get("vessel_name"),
                    "vessel_type": row.get("VesselType") or row.get("vessel_type"),
                    "imo": row.get("IMO") or row.get("imo"),
                    "callsign": row.get("CallSign") or row.get("callsign"),
                    "navigational_status": row.get("Status") or row.get("navigational_status"),
                })

        return raw_pings


class RawPingsAISProvider(AISProvider):
    """
    AIS Provider wrapping an in-memory list of raw ping dictionaries or AISPoint objects.
    """

    def __init__(self, pings: List[Union[Dict[str, Any], AISPoint]]):
        self._pings = [
            p.model_dump(mode="json") if hasattr(p, "model_dump") else dict(p)
            for p in pings
        ]

    def get_historical_positions(
        self,
        bounding_box: Optional[BoundingBox] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        if not bounding_box and not start_time and not end_time:
            return self._pings

        filtered: List[Dict[str, Any]] = []
        for p in self._pings:
            lat = float(p.get("latitude", 0.0))
            lon = float(p.get("longitude", 0.0))
            raw_t = p.get("timestamp")

            if bounding_box:
                if not (bounding_box.min_latitude <= lat <= bounding_box.max_latitude and
                        bounding_box.min_longitude <= lon <= bounding_box.max_longitude):
                    continue

            if start_time or end_time:
                try:
                    if isinstance(raw_t, datetime):
                        ts = raw_t if raw_t.tzinfo else raw_t.replace(tzinfo=timezone.utc)
                    else:
                        ts = datetime.fromisoformat(str(raw_t).replace("Z", "+00:00"))
                        if ts.tzinfo is None:
                            ts = ts.replace(tzinfo=timezone.utc)
                    if start_time and ts < start_time:
                        continue
                    if end_time and ts > end_time:
                        continue
                except Exception:
                    continue

            filtered.append(p)
        return filtered


class GlobalFishingWatchAISProvider(AISProvider):
    """
    AIS Provider connecting to external Global Fishing Watch API.
    Enforces real-data credentials verification.
    """

    def __init__(self, api_token: Optional[str] = None, api_url: Optional[str] = None):
        self.api_token = api_token or settings.gfw_api_token
        self.api_url = api_url or settings.gfw_api_url

    def get_historical_positions(
        self,
        bounding_box: Optional[BoundingBox] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        if not self.api_token:
            raise ValueError(
                "REAL mode requires GFW_API_TOKEN in .env. "
                "Set APP_MODE=DEMO to use local indexed MarineCadastre trajectory data, "
                "or provide an AIS dataset CSV filepath."
            )
        logger.info(f"Connecting to GFW AIS API at {self.api_url}")
        raise NotImplementedError("Global Fishing Watch live API integration configured.")
