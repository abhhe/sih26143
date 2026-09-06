import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel, Field

from backend.app.domain.models import (
    SpillGeometry,
    CoordinatePoint,
    ReleaseTimeWindow,
    CandidateVesselFeatures,
)
from backend.app.adapters.ais.vessel_analyzer import AISVesselAnalyzer

logger = logging.getLogger(__name__)

router = APIRouter(tags=["AIS Vessel Analysis"])
analyzer = AISVesselAnalyzer()


class AISCandidateRequest(BaseModel):
    probable_source_region: Optional[SpillGeometry] = Field(
        None, description="GeoJSON polygon of 95% KDE probable source region"
    )
    source_centroid: Optional[CoordinatePoint] = Field(
        None, description="Centroid of probable source region"
    )
    release_time_window: ReleaseTimeWindow = Field(
        ..., description="Estimated oil release time bracket"
    )
    spatial_radius_km: float = Field(
        default=25.0, ge=1.0, le=200.0, description="Configurable search corridor radius in km"
    )
    ais_dataset_path: Optional[str] = Field(
        None, description="Optional custom CSV filepath for AIS trajectory data"
    )
    raw_pings: Optional[List[Dict[str, Any]]] = Field(
        None, description="Optional in-memory list of raw AIS position ping dictionaries"
    )
    temporal_tolerance_hours: Optional[float] = Field(
        default=3.0, ge=0.0, le=48.0, description="Temporal tolerance buffer around release window (hours)"
    )
    app_mode: Optional[str] = Field(
        None, description="Runtime execution mode ('DEMO' or 'REAL')"
    )


@router.post(
    "/api/ais/analyze-candidates",
    response_model=List[CandidateVesselFeatures],
    summary="Analyze AIS vessel trajectories and extract candidate kinematic features",
    description=(
        "Executes a 10-step trajectory processing pipeline: "
        "timestamp normalization, coordinate sanitization, impossible speed removal, "
        "trajectory reconstruction, spatial and temporal filtering, closest point of approach (CPA) calculation, "
        "point-in-polygon source intersection, approach/departure bearings, speed/course statistics, "
        "route-deviation indicator, and AIS transponder gap detection. "
        "Does NOT declare culpability at this stage."
    ),
)
async def analyze_ais_candidates(
    request: AISCandidateRequest = Body(...),
) -> List[CandidateVesselFeatures]:
    try:
        ais_input = request.raw_pings if request.raw_pings is not None else request.ais_dataset_path
        candidates = analyzer.analyze_candidates(
            probable_source_region=request.probable_source_region,
            release_time_window=request.release_time_window,
            spatial_radius_km=request.spatial_radius_km,
            ais_dataset=ais_input,
            source_centroid=request.source_centroid,
            temporal_tolerance_hours=request.temporal_tolerance_hours,
            app_mode=request.app_mode,
        )
        return candidates
    except ValueError as ve:
        logger.warning(f"Validation issue during AIS candidate analysis: {ve}")
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Error during AIS candidate analysis: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
