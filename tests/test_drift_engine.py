import pytest
import math
from datetime import datetime, timezone
from pathlib import Path

from backend.app.adapters.drift.lagrangian_engine import LagrangianDriftEngine
from backend.app.adapters.metocean.environmental_service import EnvironmentalForcingService
from backend.app.interfaces.providers import IHindcastDriftEngine
from backend.app.domain.models import (
    SpillDetection,
    SpillGeometry,
    CoordinatePoint,
    BoundingBox,
    DriftResult,
)

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def mock_spill() -> SpillDetection:
    return SpillDetection(
        detected=True,
        confidence=0.95,
        centroid=CoordinatePoint(latitude=56.45, longitude=3.20),
        bounding_box=BoundingBox(
            min_latitude=56.44, min_longitude=3.18, max_latitude=56.46, max_longitude=3.22
        ),
        area=4.82,
        perimeter=11.4,
        orientation=248.5,
        spill_mask=SpillGeometry(
            type="Polygon",
            coordinates=[[[3.18, 56.44], [3.22, 56.44], [3.22, 56.46], [3.18, 56.46], [3.18, 56.44]]],
        ),
    )


@pytest.fixture
def metocean_service() -> EnvironmentalForcingService:
    return EnvironmentalForcingService(data_dir=FIXTURE_DIR, app_mode="DEMO")


def test_drift_engine_implements_interface():
    engine = LagrangianDriftEngine()
    assert isinstance(engine, IHindcastDriftEngine)


@pytest.mark.asyncio
async def test_drift_engine_determinism_with_seed(mock_spill, metocean_service):
    engine = LagrangianDriftEngine()
    obs_time = datetime(2026, 8, 14, 6, 0, tzinfo=timezone.utc)

    # Run 1
    res1 = await engine.compute_backward_drift(
        spill=mock_spill,
        observation_time=obs_time,
        metocean_provider=metocean_service,
        max_hindcast_hours=6.0,
        particle_count=25,
        timestep_minutes=30.0,
        random_seed=42,
    )

    # Run 2 with identical seed
    res2 = await engine.compute_backward_drift(
        spill=mock_spill,
        observation_time=obs_time,
        metocean_provider=metocean_service,
        max_hindcast_hours=6.0,
        particle_count=25,
        timestep_minutes=30.0,
        random_seed=42,
    )

    # Results must be strictly identical
    assert res1.source_centroid.latitude == res2.source_centroid.latitude
    assert res1.source_centroid.longitude == res2.source_centroid.longitude
    assert res1.uncertainty.spatial_radius_km == res2.uncertainty.spatial_radius_km

    # Compare particle step coordinates
    p1_step = res1.particle_trajectories[0].steps[-1]
    p2_step = res2.particle_trajectories[0].steps[-1]
    assert p1_step.latitude == p2_step.latitude
    assert p1_step.longitude == p2_step.longitude


@pytest.mark.asyncio
async def test_backward_hindcast_advection_direction(mock_spill, metocean_service):
    """
    With environmental forcing pushing Eastward (u > 0) and Northward (v > 0),
    a backward hindcast must advect particles Westward (upstream) and Southward (upwind).
    """
    engine = LagrangianDriftEngine()
    obs_time = datetime(2026, 8, 14, 6, 0, tzinfo=timezone.utc)

    result = await engine.compute_backward_drift(
        spill=mock_spill,
        observation_time=obs_time,
        metocean_provider=metocean_service,
        max_hindcast_hours=12.0,
        particle_count=30,
        timestep_minutes=30.0,
        random_seed=123,
    )

    assert isinstance(result, DriftResult)
    # Source centroid must be upstream (westward) from observed slick centroid
    assert result.source_centroid.longitude < mock_spill.centroid.longitude
    assert result.source_centroid.latitude < mock_spill.centroid.latitude
    assert result.drift_duration_hours == 12.0
    assert result.particle_count == 30


@pytest.mark.asyncio
async def test_forward_forecast_simulation(mock_spill, metocean_service):
    """
    Forward forecast must advect downstream (eastward / north-eastward).
    """
    engine = LagrangianDriftEngine()
    obs_time = datetime(2026, 8, 14, 6, 0, tzinfo=timezone.utc)

    result = await engine.compute_backward_drift(
        spill=mock_spill,
        observation_time=obs_time,
        metocean_provider=metocean_service,
        max_hindcast_hours=6.0,
        forecast_hours=6.0,
        particle_count=20,
        random_seed=777,
    )

    assert result.forward_trajectories is not None
    assert len(result.forward_trajectories) == 20

    # Final forward step should be eastward from spill centroid
    final_fwd_step = result.forward_trajectories[0].steps[-1]
    assert final_fwd_step.longitude > mock_spill.centroid.longitude


@pytest.mark.asyncio
async def test_source_envelope_and_uncertainty(mock_spill, metocean_service):
    engine = LagrangianDriftEngine()
    obs_time = datetime(2026, 8, 14, 6, 0, tzinfo=timezone.utc)

    result = await engine.compute_backward_drift(
        spill=mock_spill,
        observation_time=obs_time,
        metocean_provider=metocean_service,
        max_hindcast_hours=18.0,
        particle_count=50,
        random_seed=999,
    )

    # Uncertainty bounds
    assert result.uncertainty.spatial_radius_km > 0.5
    assert result.uncertainty.major_semi_axis_km >= result.uncertainty.minor_semi_axis_km
    assert result.uncertainty.confidence_level == 0.95

    # Source Polygon geometry
    poly = result.source_region
    assert poly.type == "Polygon"
    assert len(poly.coordinates[0]) >= 4
    # Polygon must be closed (first vertex == last vertex)
    assert poly.coordinates[0][0] == poly.coordinates[0][-1]

    # Release-Time Window
    rw = result.release_time_window
    assert rw.earliest < rw.most_probable < rw.latest < obs_time
    assert rw.slick_age_hours_range[0] < rw.slick_age_hours_range[1]
