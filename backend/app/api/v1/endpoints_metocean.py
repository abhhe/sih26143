import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel, Field

from backend.app.domain.models import EnvironmentalState, CoordinatePoint
from backend.app.adapters.metocean.environmental_service import EnvironmentalForcingService
from backend.app.adapters.metocean.custom_provider import UniformMeteoOceanProvider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/metocean", tags=["Environmental Forcing (Wind & Ocean Currents)"])


class MetoceanPointRequest(BaseModel):
    latitude: float = Field(..., ge=-90.0, le=90.0, description="Latitude in decimal degrees")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Longitude in decimal degrees")
    timestamp: Optional[datetime] = Field(None, description="UTC timestamp for conditions")
    
    # Optional manual overrides
    wind_speed_ms: Optional[float] = Field(None, ge=0.0, description="Wind speed in m/s")
    wind_direction_deg: Optional[float] = Field(None, ge=0.0, lt=360.0, description="Wind direction FROM which wind blows (0-360 deg)")
    current_speed_ms: Optional[float] = Field(None, ge=0.0, description="Surface current speed in m/s")
    current_direction_deg: Optional[float] = Field(None, ge=0.0, lt=360.0, description="Current direction TOWARDS which water sets (0-360 deg)")
    wind_u: Optional[float] = Field(None, description="Eastward wind velocity component in m/s")
    wind_v: Optional[float] = Field(None, description="Northward wind velocity component in m/s")
    current_u: Optional[float] = Field(None, description="Eastward current velocity component in m/s")
    current_v: Optional[float] = Field(None, description="Northward current velocity component in m/s")


@router.post(
    "/point",
    response_model=EnvironmentalState,
    summary="Query environmental conditions (wind + ocean currents) at a geographic point and timestamp",
    description=(
        "Retrieves atmospheric wind (ECMWF ERA5) and surface ocean current (CMEMS Copernicus Marine) vectors. "
        "Adheres strictly to standard vector conventions:\n"
        "- Wind direction: Direction FROM which wind blows (meteorological, 0-360 deg)\n"
        "- Current direction: Direction TOWARDS which water sets (oceanographic, 0-360 deg)\n"
        "Supports user-defined overrides for sensitivity analysis or localized observations."
    ),
)
async def get_metocean_point(
    request: MetoceanPointRequest = Body(...),
) -> EnvironmentalState:
    ts = request.timestamp or datetime.now(timezone.utc)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)

    # Check if overrides are provided
    has_overrides = any(
        x is not None
        for x in (
            request.wind_speed_ms,
            request.wind_direction_deg,
            request.current_speed_ms,
            request.current_direction_deg,
            request.wind_u,
            request.wind_v,
            request.current_u,
            request.current_v,
        )
    )

    try:
        if has_overrides:
            provider = UniformMeteoOceanProvider(
                wind_u=request.wind_u,
                wind_v=request.wind_v,
                current_u=request.current_u,
                current_v=request.current_v,
                wind_speed_ms=request.wind_speed_ms,
                wind_direction_deg=request.wind_direction_deg,
                current_speed_ms=request.current_speed_ms,
                current_direction_deg=request.current_direction_deg,
                source_label="User Override",
            )
            return await provider.get_environmental_state(request.latitude, request.longitude, ts)
        else:
            service = EnvironmentalForcingService()
            return await service.get_environmental_state(request.latitude, request.longitude, ts)
    except Exception as e:
        logger.error(f"Error querying metocean point: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Environmental forcing query failed: {str(e)}")


@router.get(
    "/point",
    response_model=EnvironmentalState,
    summary="Query environmental conditions via GET parameters",
)
async def get_metocean_point_get(
    latitude: float = Query(..., ge=-90.0, le=90.0),
    longitude: float = Query(..., ge=-180.0, le=180.0),
    timestamp: Optional[datetime] = Query(None),
) -> EnvironmentalState:
    ts = timestamp or datetime.now(timezone.utc)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)

    service = EnvironmentalForcingService()
    return await service.get_environmental_state(latitude, longitude, ts)
