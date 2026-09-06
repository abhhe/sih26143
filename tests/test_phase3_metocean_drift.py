import math
import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.adapters.metocean.vector_math import (
    wind_speed_dir_to_uv,
    uv_to_wind_speed_dir,
    current_speed_dir_to_uv,
    uv_to_current_speed_dir,
    knots_to_ms,
    kmh_to_ms,
)
from backend.app.adapters.metocean.custom_provider import UniformMeteoOceanProvider
from backend.app.adapters.drift.lagrangian_engine import LagrangianDriftEngine
from backend.app.domain.models import (
    SpillDetection,
    SpillGeometry,
    CoordinatePoint,
    BoundingBox,
    EnvironmentalState,
)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def sample_spill() -> SpillDetection:
    return SpillDetection(
        detected=True,
        confidence=0.96,
        centroid=CoordinatePoint(latitude=56.45, longitude=3.20),
        bounding_box=BoundingBox(
            min_latitude=56.44, min_longitude=3.18, max_latitude=56.46, max_longitude=3.22
        ),
        area=4.5,
        perimeter=10.0,
        orientation=45.0,
        spill_mask=SpillGeometry(
            type="Polygon",
            coordinates=[[[3.18, 56.44], [3.22, 56.44], [3.22, 56.46], [3.18, 56.46], [3.18, 56.44]]],
        ),
    )


# =====================================================================
# 1. Wind & Current Vector Math Tests (Meteorological vs Oceanographic)
# =====================================================================

def test_wind_vector_meteorological_conventions():
    """
    Meteorological wind direction: Direction FROM which the wind blows.
    - 0 deg (North wind): Blows FROM North TOWARDS South -> u = 0, v = -speed
    - 90 deg (East wind): Blows FROM East TOWARDS West -> u = -speed, v = 0
    - 180 deg (South wind): Blows FROM South TOWARDS North -> u = 0, v = +speed
    - 270 deg (West wind): Blows FROM West TOWARDS East -> u = +speed, v = 0
    """
    speed = 10.0

    # North wind (0 deg)
    u_n, v_n = wind_speed_dir_to_uv(speed, 0.0)
    assert math.isclose(u_n, 0.0, abs_tol=1e-5)
    assert math.isclose(v_n, -10.0, abs_tol=1e-5)
    s_back, d_back = uv_to_wind_speed_dir(u_n, v_n)
    assert math.isclose(s_back, 10.0, abs_tol=1e-2)
    assert math.isclose(d_back, 0.0, abs_tol=1e-1) or math.isclose(d_back, 360.0, abs_tol=1e-1)

    # East wind (90 deg)
    u_e, v_e = wind_speed_dir_to_uv(speed, 90.0)
    assert math.isclose(u_e, -10.0, abs_tol=1e-5)
    assert math.isclose(v_e, 0.0, abs_tol=1e-5)
    s_back, d_back = uv_to_wind_speed_dir(u_e, v_e)
    assert math.isclose(s_back, 10.0, abs_tol=1e-2)
    assert math.isclose(d_back, 90.0, abs_tol=1e-1)

    # South wind (180 deg)
    u_s, v_s = wind_speed_dir_to_uv(speed, 180.0)
    assert math.isclose(u_s, 0.0, abs_tol=1e-5)
    assert math.isclose(v_s, 10.0, abs_tol=1e-5)
    s_back, d_back = uv_to_wind_speed_dir(u_s, v_s)
    assert math.isclose(s_back, 10.0, abs_tol=1e-2)
    assert math.isclose(d_back, 180.0, abs_tol=1e-1)

    # West wind (270 deg)
    u_w, v_w = wind_speed_dir_to_uv(speed, 270.0)
    assert math.isclose(u_w, 10.0, abs_tol=1e-5)
    assert math.isclose(v_w, 0.0, abs_tol=1e-5)
    s_back, d_back = uv_to_wind_speed_dir(u_w, v_w)
    assert math.isclose(s_back, 10.0, abs_tol=1e-2)
    assert math.isclose(d_back, 270.0, abs_tol=1e-1)


def test_ocean_current_vector_oceanographic_conventions():
    """
    Oceanographic current direction: Direction TOWARDS which the water flows.
    - 0 deg (North set): Sets TOWARDS North -> u = 0, v = +speed
    - 90 deg (East set): Sets TOWARDS East -> u = +speed, v = 0
    - 180 deg (South set): Sets TOWARDS South -> u = 0, v = -speed
    - 270 deg (West set): Sets TOWARDS West -> u = -speed, v = 0
    """
    speed = 0.5

    # North current (0 deg)
    u_n, v_n = current_speed_dir_to_uv(speed, 0.0)
    assert math.isclose(u_n, 0.0, abs_tol=1e-5)
    assert math.isclose(v_n, 0.5, abs_tol=1e-5)
    s_back, d_back = uv_to_current_speed_dir(u_n, v_n)
    assert math.isclose(s_back, 0.5, abs_tol=1e-3)
    assert math.isclose(d_back, 0.0, abs_tol=1e-1) or math.isclose(d_back, 360.0, abs_tol=1e-1)

    # East current (90 deg)
    u_e, v_e = current_speed_dir_to_uv(speed, 90.0)
    assert math.isclose(u_e, 0.5, abs_tol=1e-5)
    assert math.isclose(v_e, 0.0, abs_tol=1e-5)
    s_back, d_back = uv_to_current_speed_dir(u_e, v_e)
    assert math.isclose(s_back, 0.5, abs_tol=1e-3)
    assert math.isclose(d_back, 90.0, abs_tol=1e-1)


def test_unit_conversion_helpers():
    assert math.isclose(knots_to_ms(1.94384), 1.0, abs_tol=1e-4)
    assert math.isclose(kmh_to_ms(3.6), 1.0, abs_tol=1e-4)


# =====================================================================
# 2. EnvironmentalState Domain Model & Computed Fields
# =====================================================================

def test_environmental_state_computed_properties():
    # Eastward wind (u=6.0, v=0.0): FROM West (270 deg)
    # Northward current (u=0.0, v=0.4): TOWARDS North (0 deg)
    state = EnvironmentalState(
        timestamp=datetime(2026, 8, 14, 6, 0, tzinfo=timezone.utc),
        latitude=56.45,
        longitude=3.20,
        wind_u=6.0,
        wind_v=0.0,
        current_u=0.0,
        current_v=0.4,
    )

    data = state.model_dump()
    assert "wind_speed" in data
    assert "wind_direction" in data
    assert "current_speed" in data
    assert "current_direction" in data
    assert "units" in data

    assert math.isclose(data["wind_speed"], 6.0, abs_tol=0.01)
    assert math.isclose(data["wind_direction"], 270.0, abs_tol=0.1)
    assert math.isclose(data["current_speed"], 0.4, abs_tol=0.01)
    assert math.isclose(data["current_direction"], 0.0, abs_tol=0.1)
    assert data["units"]["wind_speed"] == "m/s"


# =====================================================================
# 3. Sensitivity Testing: Same Spill with Different Wind & Current
# =====================================================================

@pytest.mark.asyncio
async def test_drift_sensitivity_to_changed_wind(sample_spill):
    """
    CRITICAL ACCEPTANCE TEST:
    Same spill advected backward under:
      - Wind Scenario A: Strong Wind from West (270 deg, 12 m/s -> pushes Eastward)
        Backward hindcast should trace source WESTWARD (lower longitude).
      - Wind Scenario B: Strong Wind from East (90 deg, 12 m/s -> pushes Westward)
        Backward hindcast should trace source EASTWARD (higher longitude).
    """
    engine = LagrangianDriftEngine()
    obs_time = datetime(2026, 8, 14, 12, 0, tzinfo=timezone.utc)

    # Wind A: From West (270 deg)
    provider_a = UniformMeteoOceanProvider(
        wind_speed_ms=12.0,
        wind_direction_deg=270.0,
        current_speed_ms=0.0,
        current_direction_deg=0.0,
    )
    res_a = await engine.compute_backward_drift(
        spill=sample_spill,
        observation_time=obs_time,
        metocean_provider=provider_a,
        max_hindcast_hours=12.0,
        particle_count=50,
        random_seed=42,
    )

    # Wind B: From East (90 deg)
    provider_b = UniformMeteoOceanProvider(
        wind_speed_ms=12.0,
        wind_direction_deg=90.0,
        current_speed_ms=0.0,
        current_direction_deg=0.0,
    )
    res_b = await engine.compute_backward_drift(
        spill=sample_spill,
        observation_time=obs_time,
        metocean_provider=provider_b,
        max_hindcast_hours=12.0,
        particle_count=50,
        random_seed=42,
    )

    # Physical verification:
    # Wind from West advects slick East; hindcast advects backward to the West (lon < spill lon)
    assert res_a.source_centroid.longitude < sample_spill.centroid.longitude
    # Wind from East advects slick West; hindcast advects backward to the East (lon > spill lon)
    assert res_b.source_centroid.longitude > sample_spill.centroid.longitude

    # Clear separation between the two source centroids
    separation_deg = abs(res_b.source_centroid.longitude - res_a.source_centroid.longitude)
    assert separation_deg > 0.15, f"Separation {separation_deg} deg is too small, wind not driving drift!"


@pytest.mark.asyncio
async def test_drift_sensitivity_to_changed_current(sample_spill):
    """
    CRITICAL ACCEPTANCE TEST:
    Same spill advected backward under:
      - Current Scenario A: Strong current towards North (0 deg, 0.8 m/s)
        Backward hindcast should trace source SOUTHWARD (lower latitude).
      - Current Scenario B: Strong current towards South (180 deg, 0.8 m/s)
        Backward hindcast should trace source NORTHWARD (higher latitude).
    """
    engine = LagrangianDriftEngine()
    obs_time = datetime(2026, 8, 14, 12, 0, tzinfo=timezone.utc)

    # Current A: Sets North (0 deg)
    provider_a = UniformMeteoOceanProvider(
        wind_speed_ms=0.0,
        wind_direction_deg=0.0,
        current_speed_ms=0.8,
        current_direction_deg=0.0,
    )
    res_a = await engine.compute_backward_drift(
        spill=sample_spill,
        observation_time=obs_time,
        metocean_provider=provider_a,
        max_hindcast_hours=10.0,
        particle_count=50,
        random_seed=42,
    )

    # Current B: Sets South (180 deg)
    provider_b = UniformMeteoOceanProvider(
        wind_speed_ms=0.0,
        wind_direction_deg=0.0,
        current_speed_ms=0.8,
        current_direction_deg=180.0,
    )
    res_b = await engine.compute_backward_drift(
        spill=sample_spill,
        observation_time=obs_time,
        metocean_provider=provider_b,
        max_hindcast_hours=10.0,
        particle_count=50,
        random_seed=42,
    )

    # Physical verification:
    # Current setting North advects slick North; hindcast traces back South (lat < spill lat)
    assert res_a.source_centroid.latitude < sample_spill.centroid.latitude
    # Current setting South advects slick South; hindcast traces back North (lat > spill lat)
    assert res_b.source_centroid.latitude > sample_spill.centroid.latitude

    separation_deg = abs(res_b.source_centroid.latitude - res_a.source_centroid.latitude)
    assert separation_deg > 0.20, f"Separation {separation_deg} deg is too small, current not driving drift!"


# =====================================================================
# 4. FastAPI Endpoints Integration Tests
# =====================================================================

def test_api_metocean_point_post(client):
    payload = {
        "latitude": 56.5,
        "longitude": 3.2,
        "wind_speed_ms": 10.0,
        "wind_direction_deg": 270.0,
        "current_speed_ms": 0.5,
        "current_direction_deg": 90.0,
    }
    response = client.post("/api/metocean/point", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["latitude"] == 56.5
    assert data["longitude"] == 3.2
    assert math.isclose(data["wind_speed"], 10.0, abs_tol=0.1)
    assert math.isclose(data["wind_direction"], 270.0, abs_tol=0.1)
    assert math.isclose(data["current_speed"], 0.5, abs_tol=0.05)
    assert math.isclose(data["current_direction"], 90.0, abs_tol=0.1)


def test_api_metocean_point_get(client):
    response = client.get("/api/metocean/point?latitude=56.5&longitude=3.2")
    assert response.status_code == 200
    data = response.json()
    assert data["latitude"] == 56.5
    assert data["longitude"] == 3.2
    assert "wind_u" in data
    assert "current_u" in data


def test_api_drift_simulate_with_coordinates(client):
    payload = {
        "latitude": 56.45,
        "longitude": 3.20,
        "area_km2": 4.5,
        "max_hindcast_hours": 6.0,
        "forecast_hours": 6.0,
        "particle_count": 25,
        "wind_speed_ms": 8.0,
        "wind_direction_deg": 225.0,
        "current_speed_ms": 0.3,
        "current_direction_deg": 45.0,
    }
    response = client.post("/api/drift/simulate", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert "drift_result" in data
    assert "environmental_snapshot" in data
    assert "model_parameters" in data

    drift = data["drift_result"]
    assert len(drift["particle_trajectories"]) == 25
    assert len(drift["forward_trajectories"]) == 25
    assert "source_centroid" in drift
    assert "uncertainty" in drift
    assert "release_time_window" in drift


def test_api_drift_simulate_with_spill_object(client, sample_spill):
    payload = {
        "spill": sample_spill.model_dump(),
        "max_hindcast_hours": 4.0,
        "particle_count": 20,
        "wind_speed_ms": 7.5,
        "wind_direction_deg": 180.0,
        "current_speed_ms": 0.25,
        "current_direction_deg": 0.0,
    }
    response = client.post("/api/drift/simulate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["drift_result"]["particle_count"] == 20
    assert data["drift_result"]["drift_duration_hours"] == 4.0
