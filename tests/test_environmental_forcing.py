import pytest
import math
from datetime import datetime, timezone
from pathlib import Path

from backend.app.adapters.metocean.environmental_service import EnvironmentalForcingService
from backend.app.interfaces.providers import IMeteoOceanProvider
from backend.app.domain.models import EnvironmentalState, BoundingBox

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


def test_service_implements_interface():
    service = EnvironmentalForcingService(data_dir=FIXTURE_DIR, app_mode="DEMO")
    assert isinstance(service, IMeteoOceanProvider)


@pytest.mark.asyncio
async def test_exact_reanalysis_node():
    service = EnvironmentalForcingService(data_dir=FIXTURE_DIR, app_mode="DEMO")
    # Exact grid node (56.50, 3.25) at exact timestamp 06:00:00Z
    t = datetime(2026, 8, 14, 6, 0, tzinfo=timezone.utc)
    state = await service.get_environmental_state(56.50, 3.25, t)

    assert isinstance(state, EnvironmentalState)
    assert state.wind_u == 6.20
    assert state.wind_v == 4.80
    assert state.current_u == 0.32
    assert state.current_v == 0.14
    assert state.quality_flags["wind"] == "EXACT_REANALYSIS_NODE"
    assert state.quality_flags["overall"] == "OPTIMAL"


@pytest.mark.asyncio
async def test_spatial_interpolation():
    service = EnvironmentalForcingService(data_dir=FIXTURE_DIR, app_mode="DEMO")
    # Halfway between nodes (56.25, 3.00) and (56.50, 3.25)
    t = datetime(2026, 8, 14, 6, 0, tzinfo=timezone.utc)
    state = await service.get_environmental_state(56.375, 3.125, t)

    assert state.quality_flags["wind"] == "SPATIALLY_INTERPOLATED"
    # Should be strictly bounded between minimum and maximum surrounding node values
    assert 5.80 <= state.wind_u <= 6.40
    assert 4.50 <= state.wind_v <= 4.90


@pytest.mark.asyncio
async def test_temporal_interpolation():
    service = EnvironmentalForcingService(data_dir=FIXTURE_DIR, app_mode="DEMO")
    # Halfway between 05:00:00Z and 06:00:00Z at exact node (56.50, 3.25)
    # At 05:00: u10 = 5.9, v10 = 4.5
    # At 06:00: u10 = 6.2, v10 = 4.8
    # Expected: u10 = 6.05, v10 = 4.65
    t = datetime(2026, 8, 14, 5, 30, tzinfo=timezone.utc)
    state = await service.get_environmental_state(56.50, 3.25, t)

    assert state.quality_flags["wind"] == "TEMPORALLY_INTERPOLATED"
    assert math.isclose(state.wind_u, 6.05, abs_tol=0.05)
    assert math.isclose(state.wind_v, 4.65, abs_tol=0.05)


@pytest.mark.asyncio
async def test_spatiotemporal_4d_interpolation():
    service = EnvironmentalForcingService(data_dir=FIXTURE_DIR, app_mode="DEMO")
    # Both spatial fractional coordinates and temporal fractional timestamp
    t = datetime(2026, 8, 14, 5, 30, tzinfo=timezone.utc)
    state = await service.get_environmental_state(56.375, 3.125, t)

    assert state.quality_flags["wind"] == "SPATIOTEMPORALLY_INTERPOLATED"
    assert 5.0 <= state.wind_u <= 7.0
    assert 4.0 <= state.wind_v <= 5.5
    assert 0.20 <= state.current_u <= 0.40


def test_direction_conventions():
    # Test meteorological wind direction (FROM which wind blows)
    # Wind with positive u (eastward) and positive v (northward) blows towards NE,
    # meaning it originates FROM South-West (225 degrees)
    state = EnvironmentalState(
        timestamp=datetime(2026, 8, 14, 6, 0, tzinfo=timezone.utc),
        latitude=56.45,
        longitude=3.20,
        wind_u=5.0,
        wind_v=5.0,
        current_u=0.30,
        current_v=0.30,
    )

    # Wind speed
    assert math.isclose(state.wind_speed, math.sqrt(50.0), abs_tol=0.05)
    # Wind direction: FROM SW = 225 deg
    assert math.isclose(state.wind_direction, 225.0, abs_tol=0.5)

    # Current speed
    assert math.isclose(state.current_speed, math.sqrt(0.18), abs_tol=0.01)
    # Current direction (oceanographic set): TOWARDS NE = 45 deg
    assert math.isclose(state.current_direction, 45.0, abs_tol=0.5)


@pytest.mark.asyncio
async def test_out_of_bounds_quality_flagging():
    service = EnvironmentalForcingService(data_dir=FIXTURE_DIR, app_mode="DEMO")
    # Query point far outside North Sea fixture domain (e.g. 70.0N, 40.0E)
    t = datetime(2026, 8, 14, 6, 0, tzinfo=timezone.utc)
    state = await service.get_environmental_state(70.0, 40.0, t)

    # Must explicitly flag out of bounds, NOT silently return 0
    assert state.quality_flags["wind"] == "SPATIALLY_OUT_OF_BOUNDS"
    assert state.quality_flags["current"] == "SPATIALLY_OUT_OF_BOUNDS"
    assert state.quality_flags["overall"] == "DEGRADED"
    assert state.wind_u is not None
    assert state.wind_u != 0.0  # Does not silently zero-fill


@pytest.mark.asyncio
async def test_get_grid_slice():
    service = EnvironmentalForcingService(data_dir=FIXTURE_DIR, app_mode="DEMO")
    bbox = BoundingBox(min_latitude=56.0, min_longitude=2.5, max_latitude=57.0, max_longitude=4.0)
    t0 = datetime(2026, 8, 14, 5, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 8, 14, 7, 0, tzinfo=timezone.utc)

    slices = await service.get_grid_slice(bbox, t0, t1)
    assert len(slices) == 3
    assert len(slices[0].lats) == 3
    assert len(slices[0].lons) == 3
