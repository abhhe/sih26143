import logging
import math
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel, Field

from backend.app.domain.models import (
    SpillDetection,
    SpillGeometry,
    CoordinatePoint,
    BoundingBox,
    DriftResult,
    EnvironmentalState,
)
from backend.app.adapters.drift.lagrangian_engine import LagrangianDriftEngine
from backend.app.adapters.metocean.environmental_service import EnvironmentalForcingService
from backend.app.adapters.metocean.custom_provider import UniformMeteoOceanProvider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/drift", tags=["Lagrangian Numerical Drift Engine"])


class DriftSimulationRequest(BaseModel):
    spill: Optional[SpillDetection] = Field(None, description="Detailed SAR spill detection object")
    latitude: Optional[float] = Field(None, ge=-90.0, le=90.0, description="Spill centroid latitude if spill object not provided")
    longitude: Optional[float] = Field(None, ge=-180.0, le=180.0, description="Spill centroid longitude if spill object not provided")
    area_km2: Optional[float] = Field(4.2, ge=0.01, description="Spill surface area in km²")
    
    observation_time: Optional[datetime] = Field(None, description="Observation UTC timestamp")
    max_hindcast_hours: float = Field(18.0, ge=1.0, le=72.0, description="Hours to simulate backward in time")
    forecast_hours: float = Field(12.0, ge=0.0, le=72.0, description="Hours to simulate forward in time")
    particle_count: int = Field(100, ge=20, le=500, description="Number of Monte Carlo Lagrangian particles")
    timestep_minutes: float = Field(30.0, ge=5.0, le=60.0, description="Numerical RK2 integration time step")
    leeway_factor: Optional[float] = Field(0.032, ge=0.01, le=0.06, description="Wind leeway transfer coefficient (typically 0.03 - 0.04)")
    leeway_deflection_deg: Optional[float] = Field(None, description="Wind deflection angle; None uses Coriolis angle")
    horizontal_diffusivity: Optional[float] = Field(5.0, ge=0.0, le=50.0, description="Eddy diffusivity in m²/s")
    random_seed: Optional[int] = Field(42, description="Random seed for deterministic trajectory reproducibility")

    # Optional environmental overrides
    wind_speed_ms: Optional[float] = Field(None, ge=0.0, description="Override wind speed in m/s")
    wind_direction_deg: Optional[float] = Field(None, ge=0.0, lt=360.0, description="Override wind direction FROM which wind blows (0-360 deg)")
    current_speed_ms: Optional[float] = Field(None, ge=0.0, description="Override surface current speed in m/s")
    current_direction_deg: Optional[float] = Field(None, ge=0.0, lt=360.0, description="Override current direction TOWARDS which water sets (0-360 deg)")
    wind_u: Optional[float] = Field(None, description="Eastward wind velocity component in m/s")
    wind_v: Optional[float] = Field(None, description="Northward wind velocity component in m/s")
    current_u: Optional[float] = Field(None, description="Eastward current velocity component in m/s")
    current_v: Optional[float] = Field(None, description="Northward current velocity component in m/s")


class DriftSimulationResponse(BaseModel):
    drift_result: DriftResult
    environmental_snapshot: EnvironmentalState
    model_parameters: Dict[str, Any]


def _build_synthetic_spill(lat: float, lon: float, area_km2: float) -> SpillDetection:
    """Generate a realistic SpillDetection polygon around a center point."""
    r_km = math.sqrt(area_km2 / math.pi)
    d_lat = r_km / 111.0
    d_lon = r_km / (111.0 * max(0.1, math.cos(math.radians(lat))))

    # 12-point elliptical polygon
    coords = []
    for i in range(13):
        angle = 2.0 * math.pi * (i % 12) / 12.0
        p_lat = lat + d_lat * math.sin(angle)
        p_lon = lon + d_lon * math.cos(angle)
        coords.append([round(p_lon, 5), round(p_lat, 5)])

    return SpillDetection(
        detected=True,
        confidence=0.95,
        centroid=CoordinatePoint(latitude=lat, longitude=lon),
        bounding_box=BoundingBox(
            min_latitude=lat - d_lat,
            max_latitude=lat + d_lat,
            min_longitude=lon - d_lon,
            max_longitude=lon + d_lon,
        ),
        area=area_km2,
        perimeter=round(2.0 * math.pi * r_km, 2),
        orientation=45.0,
        spill_mask=SpillGeometry(type="Polygon", coordinates=[coords]),
        detector_algorithm="Synthetic-Polygon-Generator",
    )


@router.post(
    "/simulate",
    response_model=DriftSimulationResponse,
    summary="Run 2nd-order Runge-Kutta (RK2) Lagrangian backward hindcast and forward forecast",
    description=(
        "Simulates Monte Carlo advection of oil particles driven by actual environmental forcing vectors:\n"
        "  - Surface ocean current (CMEMS Copernicus Marine)\n"
        "  - 10m atmospheric wind (ECMWF ERA5) with leeway advection and Coriolis deflection\n"
        "  - Horizontal turbulent Brownian diffusion\n\n"
        "Produces:\n"
        "  - Backward particle trajectories\n"
        "  - 95% Kernel Density Estimated (KDE) source region\n"
        "  - Release time window\n"
        "  - Forward forecast trajectories"
    ),
)
async def simulate_drift(
    request: DriftSimulationRequest = Body(...),
) -> DriftSimulationResponse:
    try:
        # Determine center coordinates and spill object
        if request.spill is not None:
            spill = request.spill
            center_lat = spill.centroid.latitude
            center_lon = spill.centroid.longitude
        elif request.latitude is not None and request.longitude is not None:
            center_lat = request.latitude
            center_lon = request.longitude
            spill = _build_synthetic_spill(center_lat, center_lon, request.area_km2 or 4.2)
        else:
            raise HTTPException(
                status_code=400,
                detail="Either 'spill' object or both 'latitude' and 'longitude' must be provided.",
            )

        # Standardize observation timestamp
        obs_time = request.observation_time or datetime.now(timezone.utc)
        if obs_time.tzinfo is None:
            obs_time = obs_time.replace(tzinfo=timezone.utc)

        # Determine environmental forcing provider
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

        if has_overrides:
            metocean_provider = UniformMeteoOceanProvider(
                wind_u=request.wind_u,
                wind_v=request.wind_v,
                current_u=request.current_u,
                current_v=request.current_v,
                wind_speed_ms=request.wind_speed_ms,
                wind_direction_deg=request.wind_direction_deg,
                current_speed_ms=request.current_speed_ms,
                current_direction_deg=request.current_direction_deg,
                source_label="Simulation Forcing Overrides",
            )
        else:
            metocean_provider = EnvironmentalForcingService()

        # Query environmental snapshot at spill centroid and observation time
        env_snapshot = await metocean_provider.get_environmental_state(
            center_lat, center_lon, obs_time
        )

        # Execute Lagrangian numerical drift engine
        engine = LagrangianDriftEngine(
            default_leeway_factor=request.leeway_factor or 0.032,
            default_leeway_deflection_deg=request.leeway_deflection_deg or 0.0,
            default_diffusivity=request.horizontal_diffusivity or 5.0,
        )

        drift_result = await engine.compute_backward_drift(
            spill=spill,
            observation_time=obs_time,
            metocean_provider=metocean_provider,
            max_hindcast_hours=request.max_hindcast_hours,
            particle_count=request.particle_count,
            timestep_minutes=request.timestep_minutes,
            leeway_factor=request.leeway_factor,
            leeway_deflection_deg=request.leeway_deflection_deg,
            horizontal_diffusivity=request.horizontal_diffusivity,
            random_seed=request.random_seed,
            forecast_hours=request.forecast_hours,
        )

        params_used = {
            "max_hindcast_hours": request.max_hindcast_hours,
            "forecast_hours": request.forecast_hours,
            "particle_count": request.particle_count,
            "timestep_minutes": request.timestep_minutes,
            "leeway_factor": request.leeway_factor or 0.032,
            "horizontal_diffusivity": request.horizontal_diffusivity or 5.0,
            "has_environmental_overrides": has_overrides,
        }

        return DriftSimulationResponse(
            drift_result=drift_result,
            environmental_snapshot=env_snapshot,
            model_parameters=params_used,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during drift simulation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Lagrangian drift simulation failed: {str(e)}")
