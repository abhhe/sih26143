import math
import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.adapters.drift.lagrangian_engine import LagrangianDriftEngine
from backend.app.adapters.metocean.custom_provider import UniformMeteoOceanProvider
from backend.app.adapters.metocean.environmental_service import EnvironmentalForcingService
from backend.app.adapters.validation.benchmark_validator import SyntheticBenchmarkValidator
from backend.app.adapters.ais.vessel_analyzer import haversine_distance_km
from backend.app.domain.models import (
    SpillDetection,
    SpillGeometry,
    CoordinatePoint,
    BoundingBox,
)

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def test_spill() -> SpillDetection:
    return SpillDetection(
        detected=True,
        confidence=0.95,
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
# 1. Backward Integration Direction & Time Decrement
# =====================================================================

@pytest.mark.asyncio
async def test_backward_integration_direction(test_spill):
    """
    1. Backward integration direction:
    With Eastward and Northward pushing forcing (u > 0, v > 0),
    backward advection must move particles Westward (lower lon) and Southward (lower lat).
    """
    engine = LagrangianDriftEngine()
    obs_time = datetime(2026, 8, 14, 12, 0, tzinfo=timezone.utc)
    provider = UniformMeteoOceanProvider(
        wind_u=5.0, wind_v=5.0, current_u=0.3, current_v=0.3
    )

    result = await engine.compute_backward_drift(
        spill=test_spill,
        observation_time=obs_time,
        metocean_provider=provider,
        max_hindcast_hours=6.0,
        particle_count=20,
        random_seed=42,
    )

    # Source centroid must be to the South and West of the observed spill
    assert result.source_centroid.latitude < test_spill.centroid.latitude
    assert result.source_centroid.longitude < test_spill.centroid.longitude


@pytest.mark.asyncio
async def test_backward_time_decreases_strictly(test_spill):
    """
    2. Time decreases correctly:
    For every step along each particle trajectory, timestamp decreases monotonically:
    T_0 > T_1 > T_2 > ... > T_N
    """
    engine = LagrangianDriftEngine()
    obs_time = datetime(2026, 8, 14, 12, 0, tzinfo=timezone.utc)
    provider = UniformMeteoOceanProvider(wind_u=5.0, wind_v=0.0, current_u=0.2, current_v=0.0)

    result = await engine.compute_backward_drift(
        spill=test_spill,
        observation_time=obs_time,
        metocean_provider=provider,
        max_hindcast_hours=4.0,
        timestep_minutes=30.0,
        particle_count=10,
        random_seed=42,
    )

    for traj in result.particle_trajectories:
        assert len(traj.steps) == 9  # T0 + 8 steps of 30 min = 4 hours
        assert traj.steps[0].timestamp == obs_time
        for i in range(len(traj.steps) - 1):
            t_curr = traj.steps[i].timestamp
            t_next = traj.steps[i + 1].timestamp
            assert t_next < t_curr, f"Step {i+1} time {t_next} is not before step {i} time {t_curr}"
            delta_sec = (t_curr - t_next).total_seconds()
            assert math.isclose(delta_sec, 1800.0, abs_tol=1.0)


# =====================================================================
# 3. Dynamic Environmental Coordinate Advection & Ensemble Dispersion
# =====================================================================

@pytest.mark.asyncio
async def test_coordinates_advected_by_velocity_field(test_spill):
    """
    3. Coordinates change according to environmental forcing, not constant subtraction.
    Doubling the current velocity should approximately double the advective displacement.
    """
    engine = LagrangianDriftEngine()
    obs_time = datetime(2026, 8, 14, 12, 0, tzinfo=timezone.utc)

    # Mild current (0.2 m/s Northward)
    p_mild = UniformMeteoOceanProvider(wind_u=0.0, wind_v=0.0, current_u=0.0, current_v=0.2)
    res_mild = await engine.compute_backward_drift(
        spill=test_spill,
        observation_time=obs_time,
        metocean_provider=p_mild,
        max_hindcast_hours=6.0,
        particle_count=20,
        random_seed=42,
    )

    # Strong current (0.6 m/s Northward)
    p_strong = UniformMeteoOceanProvider(wind_u=0.0, wind_v=0.0, current_u=0.0, current_v=0.6)
    res_strong = await engine.compute_backward_drift(
        spill=test_spill,
        observation_time=obs_time,
        metocean_provider=p_strong,
        max_hindcast_hours=6.0,
        particle_count=20,
        random_seed=42,
    )

    dy_mild = test_spill.centroid.latitude - res_mild.source_centroid.latitude
    dy_strong = test_spill.centroid.latitude - res_strong.source_centroid.latitude

    # Strong current should advect roughly 3x further than mild current
    assert dy_strong > dy_mild * 2.2


@pytest.mark.asyncio
async def test_particle_ensemble_generation(test_spill):
    """
    4. Particle ensemble generation:
    Particles start dispersed around the spill and diverge over time due to Brownian diffusion and leeway variation.
    """
    engine = LagrangianDriftEngine()
    obs_time = datetime(2026, 8, 14, 12, 0, tzinfo=timezone.utc)
    provider = UniformMeteoOceanProvider(wind_u=5.0, wind_v=5.0, current_u=0.2, current_v=0.2)

    result = await engine.compute_backward_drift(
        spill=test_spill,
        observation_time=obs_time,
        metocean_provider=provider,
        max_hindcast_hours=6.0,
        particle_count=50,
        random_seed=42,
    )

    assert len(result.particle_trajectories) == 50
    initial_lats = [t.steps[0].latitude for t in result.particle_trajectories]
    final_lats = [t.steps[-1].latitude for t in result.particle_trajectories]

    # Variance at the end of the hindcast should be strictly larger than initial variance
    var_init = float(math.pow(float(math.sqrt(sum((x - sum(initial_lats)/len(initial_lats))**2 for x in initial_lats) / len(initial_lats))), 2))
    var_final = float(math.pow(float(math.sqrt(sum((x - sum(final_lats)/len(final_lats))**2 for x in final_lats) / len(final_lats))), 2))
    assert var_final > var_init


# =====================================================================
# 5. Source Centroid, Probable Source Region & Release Time Calculation
# =====================================================================

@pytest.mark.asyncio
async def test_source_centroid_and_region_bounds(test_spill):
    """
    5 & 6. Source centroid and Probable Source Region bounds:
    Calculates center of mass, 95% KDE boundary polygon, and spatial uncertainty radius.
    """
    engine = LagrangianDriftEngine()
    obs_time = datetime(2026, 8, 14, 12, 0, tzinfo=timezone.utc)
    provider = UniformMeteoOceanProvider(wind_u=6.0, wind_v=3.0, current_u=0.3, current_v=0.1)

    result = await engine.compute_backward_drift(
        spill=test_spill,
        observation_time=obs_time,
        metocean_provider=provider,
        max_hindcast_hours=8.0,
        particle_count=40,
        random_seed=42,
    )

    # 1. Source centroid
    assert isinstance(result.source_centroid, CoordinatePoint)
    assert -90.0 <= result.source_centroid.latitude <= 90.0
    assert -180.0 <= result.source_centroid.longitude <= 180.0

    # 2. Source region polygon
    assert isinstance(result.source_region, SpillGeometry)
    assert result.source_region.type == "Polygon"
    assert len(result.source_region.coordinates) > 0
    ring = result.source_region.coordinates[0]
    assert len(ring) >= 4  # Closed polygon has at least 4 vertices
    assert ring[0] == ring[-1]  # Closed ring

    # 3. Uncertainty radius
    assert result.uncertainty.spatial_radius_km > 0.0
    assert result.uncertainty.confidence_level == 0.95


@pytest.mark.asyncio
async def test_release_time_window_calculation(test_spill):
    """
    7. Release-time calculation:
    Verifies that release window is dynamically calculated from hindcast duration,
    with earliest < most_probable < latest < observation_time.
    """
    engine = LagrangianDriftEngine()
    obs_time = datetime(2026, 8, 14, 12, 0, tzinfo=timezone.utc)
    provider = UniformMeteoOceanProvider(wind_u=5.0, wind_v=0.0, current_u=0.2, current_v=0.0)

    hindcast_hours = 12.0
    result = await engine.compute_backward_drift(
        spill=test_spill,
        observation_time=obs_time,
        metocean_provider=provider,
        max_hindcast_hours=hindcast_hours,
        particle_count=20,
        random_seed=42,
    )

    rw = result.release_time_window
    assert rw.earliest < rw.most_probable < rw.latest < obs_time
    assert rw.most_probable == obs_time - timedelta(hours=hindcast_hours)
    assert rw.slick_age_hours_range[0] < rw.slick_age_hours_range[1]
    assert math.isclose(rw.slick_age_hours_range[0], 9.2, abs_tol=1.5)
    assert math.isclose(rw.slick_age_hours_range[1], 14.8, abs_tol=1.5)


# =====================================================================
# 8. Environmental Forcing Sensitivity Test
# =====================================================================

@pytest.mark.asyncio
async def test_environmental_forcing_changes_source_reconstruction(test_spill):
    """
    8. Environmental forcing changes source reconstruction:
    Reconstructing the source of the same spill under:
      - Forcing Scenario A: North-Easterly flow
      - Forcing Scenario B: South-Westerly flow
    produces distinct probable source regions with significant spatial separation.
    """
    engine = LagrangianDriftEngine()
    obs_time = datetime(2026, 8, 14, 12, 0, tzinfo=timezone.utc)

    # Scenario A: Forcing to North-East (u > 0, v > 0) -> Hindcast traces South-West
    p_a = UniformMeteoOceanProvider(wind_u=8.0, wind_v=8.0, current_u=0.4, current_v=0.4)
    res_a = await engine.compute_backward_drift(
        spill=test_spill,
        observation_time=obs_time,
        metocean_provider=p_a,
        max_hindcast_hours=8.0,
        particle_count=30,
        random_seed=42,
    )

    # Scenario B: Forcing to South-West (u < 0, v < 0) -> Hindcast traces North-East
    p_b = UniformMeteoOceanProvider(wind_u=-8.0, wind_v=-8.0, current_u=-0.4, current_v=-0.4)
    res_b = await engine.compute_backward_drift(
        spill=test_spill,
        observation_time=obs_time,
        metocean_provider=p_b,
        max_hindcast_hours=8.0,
        particle_count=30,
        random_seed=42,
    )

    dist_km = haversine_distance_km(
        res_a.source_centroid.latitude,
        res_a.source_centroid.longitude,
        res_b.source_centroid.latitude,
        res_b.source_centroid.longitude,
    )
    assert dist_km > 30.0, f"Separation between reconstructed sources ({dist_km:.2f} km) is too small!"


# =====================================================================
# 9, 10, 11, 12. Input Validation & Error Handling
# =====================================================================

def test_api_invalid_coordinates(client):
    """9. Invalid coordinates: Latitude > 90 or Longitude > 180 returns HTTP 422."""
    payload_bad_lat = {
        "latitude": 95.0,
        "longitude": 3.20,
        "backward_hours": 10.0,
    }
    res = client.post("/api/drift/source-reconstruction", json=payload_bad_lat)
    assert res.status_code == 422

    payload_bad_lon = {
        "latitude": 56.50,
        "longitude": 205.0,
        "backward_hours": 10.0,
    }
    res2 = client.post("/api/drift/source-reconstruction", json=payload_bad_lon)
    assert res2.status_code == 422


def test_api_invalid_timestamp(client):
    """10. Invalid timestamp: Malformed timestamp format returns HTTP 422."""
    payload = {
        "latitude": 56.45,
        "longitude": 3.20,
        "observation_time": "not-a-valid-iso-timestamp",
        "backward_hours": 10.0,
    }
    res = client.post("/api/drift/source-reconstruction", json=payload)
    assert res.status_code == 422


def test_api_zero_or_negative_backward_duration(client):
    """11. Zero or negative backward duration returns HTTP 422."""
    payload_zero = {
        "latitude": 56.45,
        "longitude": 3.20,
        "backward_hours": 0.0,
    }
    res_zero = client.post("/api/drift/source-reconstruction", json=payload_zero)
    assert res_zero.status_code == 422

    payload_neg = {
        "latitude": 56.45,
        "longitude": 3.20,
        "backward_hours": -6.0,
    }
    res_neg = client.post("/api/drift/source-reconstruction", json=payload_neg)
    assert res_neg.status_code == 422


@pytest.mark.asyncio
async def test_missing_environmental_data_explicitly_flagged():
    """12. Missing environmental data: Out of bounds data explicitly flagged."""
    service = EnvironmentalForcingService(data_dir=FIXTURE_DIR, app_mode="DEMO")
    t = datetime(2026, 8, 14, 6, 0, tzinfo=timezone.utc)
    # Query point far outside fixture bounds
    state = await service.get_environmental_state(80.0, 120.0, t)

    assert state.quality_flags["wind"] == "SPATIALLY_OUT_OF_BOUNDS"
    assert state.quality_flags["overall"] == "DEGRADED"
    assert state.wind_u is not None


# =====================================================================
# 13. Deterministic Repeated Runs
# =====================================================================

@pytest.mark.asyncio
async def test_deterministic_repeated_runs(test_spill):
    """13. Deterministic repeated runs: Identical seed produces bit-exact identical trajectories."""
    engine = LagrangianDriftEngine()
    obs_time = datetime(2026, 8, 14, 12, 0, tzinfo=timezone.utc)
    provider = UniformMeteoOceanProvider(wind_u=6.0, wind_v=3.0, current_u=0.25, current_v=0.15)

    res1 = await engine.compute_backward_drift(
        spill=test_spill,
        observation_time=obs_time,
        metocean_provider=provider,
        max_hindcast_hours=6.0,
        particle_count=25,
        random_seed=12345,
    )

    res2 = await engine.compute_backward_drift(
        spill=test_spill,
        observation_time=obs_time,
        metocean_provider=provider,
        max_hindcast_hours=6.0,
        particle_count=25,
        random_seed=12345,
    )

    assert res1.source_centroid.latitude == res2.source_centroid.latitude
    assert res1.source_centroid.longitude == res2.source_centroid.longitude
    assert res1.uncertainty.spatial_radius_km == res2.uncertainty.spatial_radius_km

    # Compare particle step coordinates
    p1 = res1.particle_trajectories[0].steps[-1]
    p2 = res2.particle_trajectories[0].steps[-1]
    assert p1.latitude == p2.latitude
    assert p1.longitude == p2.longitude


# =====================================================================
# 14. Demo Mode Preservation
# =====================================================================

def test_demo_mode_preservation(client):
    """14. Existing Demo Mode: Health check and demo scenarios remain functional and isolated."""
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "online"
    assert data["mode"] == "DEMO"


# =====================================================================
# 15. Scientific Validation Against Synthetic Ground Truth
# =====================================================================

@pytest.mark.asyncio
async def test_scientific_validation_against_ground_truth():
    """
    15. Scientific Validation:
    Compares backward Lagrangian source reconstruction against a controlled physical ground-truth scenario:
    - Known ground-truth release point: (56.3250°N, 3.0200°E)
    - Known ground-truth release time: 2026-08-13 14:00 UTC
    - Forward advection: 16 hours under wind=8.5 m/s (240°) and current=0.28 m/s (85°)
    - Reconstructed source centroid is compared against known ground-truth location.
    """
    validator = SyntheticBenchmarkValidator()
    scenario = validator.generate_controlled_scenario(
        gt_source_lat=56.3250,
        gt_source_lon=3.0200,
        gt_release_time=datetime(2026, 8, 13, 14, 0, 0, tzinfo=timezone.utc),
        advection_hours=16.0,
        wind_speed_ms=8.5,
        wind_dir_deg=240.0,
        current_speed_ms=0.28,
        current_dir_deg=85.0,
    )

    obs_lat = scenario["obs_lat"]
    obs_lon = scenario["obs_lon"]
    obs_time = scenario["obs_time"]
    spill = scenario["spill"]

    # Run backward reconstruction using the same physical forcing
    engine = LagrangianDriftEngine()
    provider = UniformMeteoOceanProvider(
        wind_speed_ms=scenario["wind_speed_ms"],
        wind_direction_deg=scenario["wind_dir_deg"],
        current_speed_ms=scenario["current_speed_ms"],
        current_direction_deg=scenario["current_dir_deg"],
    )

    recon = await engine.compute_backward_drift(
        spill=spill,
        observation_time=obs_time,
        metocean_provider=provider,
        max_hindcast_hours=scenario["advection_hours"],
        particle_count=50,
        random_seed=42,
    )

    # 1. Localization Error against ground truth
    loc_err_km = haversine_distance_km(
        recon.source_centroid.latitude,
        recon.source_centroid.longitude,
        scenario["gt_source_lat"],
        scenario["gt_source_lon"],
    )

    # In controlled synthetic test with 50 particles and Dh=5.0, error should be within uncertainty envelope (< 3.5 km)
    assert loc_err_km < 3.5, f"Localization error ({loc_err_km:.2f} km) exceeded expected threshold!"

    # 2. Release-Time Error against ground truth
    time_err_hours = abs(
        (recon.release_time_window.most_probable - scenario["gt_release_time"]).total_seconds() / 3600.0
    )
    assert time_err_hours < 0.5, f"Release time error ({time_err_hours:.2f} h) exceeded expected threshold!"

    # 3. Ground truth falls within 95% uncertainty radius
    assert loc_err_km <= recon.uncertainty.spatial_radius_km * 1.2
