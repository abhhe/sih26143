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
    DriftUncertainty,
    ReleaseTimeWindow,
    ParticleTrajectory,
    EnvironmentalState,
)
from backend.app.adapters.drift.lagrangian_engine import LagrangianDriftEngine
from backend.app.adapters.metocean.environmental_service import EnvironmentalForcingService
from backend.app.adapters.metocean.custom_provider import UniformMeteoOceanProvider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/drift", tags=["Lagrangian Numerical Drift & Source Reconstruction"])


class DriftSimulationRequest(BaseModel):
    spill: Optional[SpillDetection] = Field(None, description="Detailed SAR spill detection object")
    latitude: Optional[float] = Field(None, ge=-90.0, le=90.0, description="Spill centroid latitude if spill object not provided")
    longitude: Optional[float] = Field(None, ge=-180.0, le=180.0, description="Spill centroid longitude if spill object not provided")
    area_km2: Optional[float] = Field(4.2, gt=0.0, description="Spill surface area in km²")
    
    observation_time: Optional[datetime] = Field(None, description="Observation UTC timestamp")
    max_hindcast_hours: Optional[float] = Field(18.0, gt=0.0, le=72.0, description="Hours to simulate backward in time")
    backward_hours: Optional[float] = Field(None, gt=0.0, le=72.0, description="Alias for max_hindcast_hours")
    
    timestep_minutes: Optional[float] = Field(30.0, gt=0.0, le=60.0, description="Numerical RK2 integration time step in minutes")
    time_step_minutes: Optional[float] = Field(None, gt=0.0, le=60.0, description="Alias for timestep_minutes")
    
    forecast_hours: float = Field(12.0, ge=0.0, le=72.0, description="Hours to simulate forward in time")
    particle_count: int = Field(100, ge=1, le=500, description="Number of Monte Carlo Lagrangian particles")
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


class SourceReconstructionResponse(BaseModel):
    source_region: SpillGeometry = Field(..., description="95% KDE Probable Source Region Polygon")
    source_region_50: Optional[SpillGeometry] = Field(None, description="50% Core Credible Zone Polygon")
    source_region_90: Optional[SpillGeometry] = Field(None, description="90% Credible Zone Polygon")
    source_centroid: CoordinatePoint = Field(..., description="Estimated probable source centroid coordinates")
    uncertainty: DriftUncertainty = Field(..., description="Dispersion metrics and uncertainty bounds")
    release_window: ReleaseTimeWindow = Field(..., description="Estimated oil release time bracket")
    backward_trajectory: List[ParticleTrajectory] = Field(..., description="Ensemble of backward-advected particle paths")
    forward_trajectory: Optional[List[ParticleTrajectory]] = Field(default_factory=list, description="Forward forecast trajectories")
    environmental_snapshot: EnvironmentalState = Field(..., description="Metocean forcing snapshot at observation")
    quality: Dict[str, Any] = Field(..., description="Simulation quality metadata and data provenance")
    scientific_disclaimer: str = Field(
        default=(
            "Probable source region and release window represent a probabilistic ensemble reconstruction "
            "advected under numerical Runge-Kutta 2nd-order (RK2) integration with ERA5 wind and CMEMS ocean current forcing. "
            "Uncertainties stem from environmental reanalysis grid resolution, empirical leeway parameterization (3.2%), "
            "and unresolved sub-mesoscale turbulent diffusion. Operational certainty cannot be claimed without in-situ ground validation."
        ),
        description="Scientific limitations and uncertainty disclaimer",
    )


def _build_synthetic_spill(lat: float, lon: float, area_km2: float) -> SpillDetection:
    """Generate a realistic SpillDetection polygon around a center point."""
    r_km = math.sqrt(max(0.01, area_km2) / math.pi)
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


async def _execute_drift_simulation(
    request: DriftSimulationRequest,
) -> Tuple[DriftResult, EnvironmentalState, Dict[str, Any]]:
    """Shared core numerical integration pipeline for drift simulation and source reconstruction."""
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

    # Validate coordinate ranges strictly
    if not (-90.0 <= center_lat <= 90.0):
        raise HTTPException(status_code=422, detail=f"Latitude {center_lat} out of range [-90.0, 90.0].")
    if not (-180.0 <= center_lon <= 180.0):
        raise HTTPException(status_code=422, detail=f"Longitude {center_lon} out of range [-180.0, 180.0].")

    # Resolve backward duration
    backward_hours = request.backward_hours or request.max_hindcast_hours or 18.0
    if backward_hours <= 0.0:
        raise HTTPException(status_code=422, detail="Backward duration must be strictly greater than zero.")

    # Resolve timestep
    step_minutes = request.time_step_minutes or request.timestep_minutes or 30.0
    if step_minutes <= 0.0:
        raise HTTPException(status_code=422, detail="Time step must be strictly greater than zero.")

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
        max_hindcast_hours=backward_hours,
        particle_count=request.particle_count,
        timestep_minutes=step_minutes,
        leeway_factor=request.leeway_factor,
        leeway_deflection_deg=request.leeway_deflection_deg,
        horizontal_diffusivity=request.horizontal_diffusivity,
        random_seed=request.random_seed,
        forecast_hours=request.forecast_hours,
    )

    params_used = {
        "max_hindcast_hours": backward_hours,
        "forecast_hours": request.forecast_hours,
        "particle_count": request.particle_count,
        "timestep_minutes": step_minutes,
        "leeway_factor": request.leeway_factor or 0.032,
        "horizontal_diffusivity": request.horizontal_diffusivity or 5.0,
        "has_environmental_overrides": has_overrides,
        "integration_scheme": "Runge-Kutta 2nd-Order Midpoint (RK2)",
    }

    return drift_result, env_snapshot, params_used


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
        drift_result, env_snapshot, params_used = await _execute_drift_simulation(request)
        return DriftSimulationResponse(
            drift_result=drift_result,
            environmental_snapshot=env_snapshot,
            model_parameters=params_used,
        )
    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(status_code=422, detail=str(ve))
    except Exception as e:
        logger.error(f"Error during drift simulation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Lagrangian drift simulation failed: {str(e)}")


@router.post(
    "/source-reconstruction",
    response_model=SourceReconstructionResponse,
    summary="Perform backward Lagrangian source reconstruction to estimate Probable Source Region and Release Window",
    description=(
        "Integrates oil slick particles backward in time from observation timestamp T to T - N*dt.\n"
        "Computes:\n"
        "  - Probable Source Region polygon (95% KDE boundary)\n"
        "  - Probable Source Centroid\n"
        "  - 95% Uncertainty dispersion bounds\n"
        "  - Probable Release Time bracket\n"
        "  - Ensemble particle trajectories"
    ),
)
@router.post(
    "/backward",
    response_model=SourceReconstructionResponse,
    summary="Alias for /api/drift/source-reconstruction",
)
async def reconstruct_source(
    request: DriftSimulationRequest = Body(...),
) -> SourceReconstructionResponse:
    try:
        drift_result, env_snapshot, params_used = await _execute_drift_simulation(request)

        quality_meta = {
            "integration_scheme": params_used.get("integration_scheme"),
            "particle_count": drift_result.particle_count,
            "backward_duration_hours": drift_result.drift_duration_hours,
            "timestep_minutes": params_used.get("timestep_minutes"),
            "forcing_quality": env_snapshot.quality_flags,
            "forcing_source": env_snapshot.source,
            "deterministic_seed": request.random_seed,
        }

        return SourceReconstructionResponse(
            source_region=drift_result.source_region,
            source_region_50=drift_result.source_region_50,
            source_region_90=drift_result.source_region_90,
            source_centroid=drift_result.source_centroid,
            uncertainty=drift_result.uncertainty,
            release_window=drift_result.release_time_window,
            backward_trajectory=drift_result.particle_trajectories,
            forward_trajectory=drift_result.forward_trajectories or [],
            environmental_snapshot=env_snapshot,
            quality=quality_meta,
        )
    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(status_code=422, detail=str(ve))
    except Exception as e:
        logger.error(f"Error during source reconstruction: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Source reconstruction failed: {str(e)}")
