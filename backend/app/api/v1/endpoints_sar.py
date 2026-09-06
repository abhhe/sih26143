import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Body
from pydantic import BaseModel

from backend.app.core.config import settings
from backend.app.domain.models import (
    SatelliteObservation,
    SpillDetection,
)
from backend.app.adapters.detection.spill_detector import SARSpillDetector
from backend.app.adapters.sar.sentinel1_adapter import Sentinel1Adapter

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Satellite SAR Analysis"])
detector = SARSpillDetector()
sar_adapter = Sentinel1Adapter()


class AnalyzeRequestJSON(BaseModel):
    image_id: Optional[str] = None
    image_path: Optional[str] = None
    latitude: float = 56.45
    longitude: float = 3.20
    resolution: float = 10.0
    sensor: str = "Sentinel-1A C-SAR"
    confidence_threshold: float = 0.50


@router.post(
    "/api/satellite/analyze",
    response_model=SpillDetection,
    summary="Analyze Sentinel-1 SAR imagery for oil spill detection and characterization",
    description="Processes SAR imagery through radiometric calibration, Refined Lee speckle filtering, adaptive dark-spot segmentation, 2nd-order spatial moments, and look-alike discrimination.",
)
async def analyze_sar_scene(
    file: Optional[UploadFile] = File(None),
    image_id: Optional[str] = Form(None),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    resolution: Optional[float] = Form(None),
    confidence_threshold: float = Form(0.50),
) -> SpillDetection:
    """
    Endpoint accepting either:
      1. Multipart form-data with uploaded SAR raster file (.tiff, .png, .jpg)
      2. Metadata referencing an existing granule image_id or local path
    """
    target_path = Path("data/sample_sar/uploaded_scene.tiff")

    if file is not None:
        # Save uploaded file temporarily to data/sample_sar
        settings.ensure_directories()
        target_path = settings.sar_data_dir / file.filename
        try:
            content = await file.read()
            with open(target_path, "wb") as f:
                f.write(content)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to process uploaded file: {e}")

        obs = SatelliteObservation(
            image_id=image_id or file.filename or "UPLOADED_SCENE",
            timestamp=datetime.utcnow(),
            latitude=latitude if latitude is not None else 56.45,
            longitude=longitude if longitude is not None else 3.20,
            image_path=str(target_path),
            sensor="Sentinel-1A C-SAR",
            resolution=resolution if resolution is not None else 10.0,
            polarization=["VV", "VH"],
        )
    elif image_id is not None:
        # Retrieve observation metadata via Sentinel1Adapter
        obs = await sar_adapter.get_observation_by_id(image_id)
        if latitude is not None:
            obs.latitude = latitude
        if longitude is not None:
            obs.longitude = longitude
    else:
        # Fallback to default demo observation
        obs = await sar_adapter.get_observation_by_id("S1A_IW_GRDH_1SDV_20260814T061522_054321_066F12_B1A4")

    # Run detection pipeline
    result = await detector.detect_spill(obs, confidence_threshold=confidence_threshold)
    return result
