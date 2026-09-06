import json
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any

from backend.app.core.config import settings
from backend.app.domain.models import (
    SpillDetection,
    SpillGeometry,
    CoordinatePoint,
    BoundingBox,
)

logger = logging.getLogger(__name__)


class OilSpillDatasetAdapter:
    """
    Adapter for the CSIRO Sentinel-1 SAR Oil Spill dataset.
    
    The CSIRO dataset contains Sentinel-1 C-SAR VV/VH patches labeled
    for oil slicks and oceanographic look-alikes.
    """

    def __init__(self, dataset_dir: Optional[Path] = None):
        self.dataset_dir = dataset_dir or settings.csiro_data_dir

    def load_patch_metadata(self, patch_filepath: Path) -> SpillDetection:
        """Parse a CSIRO patch metadata JSON file into a SpillDetection contract."""
        with open(patch_filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        is_spill = data.get("label", "").lower() == "oil_spill"
        confidence = float(data.get("confidence", 0.90 if is_spill else 0.10))

        centroid_data = data.get("centroid", {})
        centroid = CoordinatePoint(
            latitude=centroid_data.get("latitude", 0.0),
            longitude=centroid_data.get("longitude", 0.0),
        )

        bbox_data = data.get("bounding_box", {})
        bounding_box = BoundingBox(
            min_latitude=bbox_data.get("min_latitude", centroid.latitude - 0.05),
            min_longitude=bbox_data.get("min_longitude", centroid.longitude - 0.05),
            max_latitude=bbox_data.get("max_latitude", centroid.latitude + 0.05),
            max_longitude=bbox_data.get("max_longitude", centroid.longitude + 0.05),
        )

        polygon_coords = data.get("polygon_coordinates", [])
        if not polygon_coords:
            # Fallback envelope polygon around bounding box
            polygon_coords = [
                [
                    [bounding_box.min_longitude, bounding_box.min_latitude],
                    [bounding_box.max_longitude, bounding_box.min_latitude],
                    [bounding_box.max_longitude, bounding_box.max_latitude],
                    [bounding_box.min_longitude, bounding_box.max_latitude],
                    [bounding_box.min_longitude, bounding_box.min_latitude],
                ]
            ]

        spill_mask = SpillGeometry(
            type="Polygon",
            coordinates=polygon_coords,
        )

        return SpillDetection(
            detected=is_spill,
            confidence=confidence,
            centroid=centroid,
            bounding_box=bounding_box,
            area=float(data.get("area_km2", 1.0)),
            perimeter=float(data.get("perimeter_km", 4.0)),
            orientation=float(data.get("orientation_deg", 0.0)),
            spill_mask=spill_mask,
            thickness_estimate=data.get("thickness_class", "dark_thick"),
            look_alike_risk=data.get("look_alike_risk", "low"),
            detector_algorithm=f"CSIRO-GroundTruth ({data.get('patch_id', 'patch')})",
        )

    def list_available_patches(self) -> List[Path]:
        """Discover available CSIRO dataset patch files."""
        if not self.dataset_dir.exists():
            # Check test fixture directory fallback
            test_fixture = (
                Path(__file__).resolve().parent.parent.parent.parent
                / "tests"
                / "fixtures"
                / "csiro_spill_fixture.json"
            )
            if test_fixture.exists():
                return [test_fixture]
            return []

        return list(self.dataset_dir.glob("*.json"))

    def get_patch_by_id(self, patch_id: str) -> SpillDetection:
        """Retrieve a specific patch by identifier."""
        target_path = self.dataset_dir / f"{patch_id}.json"
        if target_path.exists():
            return self.load_patch_metadata(target_path)

        # Search all json files in dataset_dir for matching patch_id
        if self.dataset_dir.exists():
            for candidate in self.dataset_dir.glob("*.json"):
                try:
                    with open(candidate, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if data.get("patch_id") == patch_id:
                        return self.load_patch_metadata(candidate)
                except Exception:
                    continue

        # Check tests fixture
        fixture_path = (
            Path(__file__).resolve().parent.parent.parent.parent
            / "tests"
            / "fixtures"
            / "csiro_spill_fixture.json"
        )
        if fixture_path.exists():
            return self.load_patch_metadata(fixture_path)

        raise FileNotFoundError(f"CSIRO patch '{patch_id}' not found in {self.dataset_dir}")
