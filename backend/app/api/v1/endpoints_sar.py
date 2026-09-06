import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Body
from pydantic import BaseModel

from PIL import Image

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

SUPPORTED_EXTENSIONS = {".tiff", ".tif", ".png", ".jpg", ".jpeg"}


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
      1. Multipart form-data with uploaded SAR raster file (.tiff, .png, .jpg, .jpeg)
      2. Metadata referencing an existing granule image_id or local path
    """
    if file is not None:
        if not file.filename:
            raise HTTPException(status_code=400, detail="Uploaded file missing filename.")

        ext = Path(file.filename).suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            supported_str = ", ".join(sorted(SUPPORTED_EXTENSIONS))
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file format '{ext}'. Supported SAR formats are: {supported_str}",
            )

        # Save uploaded file temporarily to data/sample_sar
        settings.ensure_directories()
        target_path = settings.sar_data_dir / file.filename
        try:
            content = await file.read()
            if len(content) == 0:
                raise HTTPException(status_code=400, detail="Uploaded file is empty (0 bytes).")
            with open(target_path, "wb") as f:
                f.write(content)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to save uploaded file: {e}")

        # Verify image format and integrity with PIL
        try:
            with Image.open(target_path) as img:
                img.verify()
        except Exception as e:
            if target_path.exists():
                try:
                    target_path.unlink()
                except OSError:
                    pass
            raise HTTPException(
                status_code=400,
                detail=f"Invalid or corrupted image file: {e}",
            )

        obs = SatelliteObservation(
            image_id=image_id or file.filename or "UPLOADED_SCENE",
            timestamp=datetime.now(timezone.utc),
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
    try:
        result = await detector.detect_spill(obs, confidence_threshold=confidence_threshold)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"SAR detection error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"SAR processing failure: {str(e)}")
