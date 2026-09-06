import math
import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.domain.models import (
    AISPoint,
    AISTrajectory,
    CoordinatePoint,
    SpillGeometry,
    ReleaseTimeWindow,
    SpeedStatistics,
    CourseStatistics,
    CandidateVesselFeatures,
)
from backend.app.adapters.ais.vessel_analyzer import (
    AISVesselAnalyzer,
    haversine_distance_km,
    point_in_polygon,
    segments_intersect,
)
from backend.app.adapters.ais.ais_provider import (
    CSVAISProvider,
    RawPingsAISProvider,
    GlobalFishingWatchAISProvider,
)


@pytest.fixture
def analyzer():
    return AISVesselAnalyzer()


@pytest.fixture
def north_sea_source():
    # Probable source region near North Sea 56.325°N, 3.020°E
    polygon_ring = [
        [3.0000, 56.3100],
        [3.0400, 56.3100],
        [3.0400, 56.3400],
        [3.0000, 56.3400],
        [3.0000, 56.3100],
    ]
    centroid = CoordinatePoint(latitude=56.3250, longitude=3.0200)
    source_geom = SpillGeometry(type="Polygon", coordinates=[polygon_ring])
    window = ReleaseTimeWindow(
        earliest=datetime(2026, 8, 13, 11, 0, 0, tzinfo=timezone.utc),
        latest=datetime(2026, 8, 13, 16, 0, 0, tzinfo=timezone.utc),
        most_probable=datetime(2026, 8, 13, 13, 30, 0, tzinfo=timezone.utc),
        slick_age_hours_range=(14.0, 19.0),
    )
    return source_geom, centroid, window


# =============================================================================
# 1. AIS Schema Validation
# =============================================================================
def test_1_ais_schema_validation():
    pt = AISPoint(
        mmsi="244123456",
        timestamp=datetime(2026, 8, 13, 12, 0, 0, tzinfo=timezone.utc),
        latitude=56.30,
        longitude=3.00,
        speed=14.5,
        course=45.0,
        heading=46.0,
        vessel_name="MT TESTER",
        imo="IMO9284123",
        callsign="PCDE",
        vessel_type="Tanker",
        navigational_status="under way using engine",
    )
    assert pt.mmsi == "244123456"
    assert pt.latitude == 56.30
    assert pt.speed == 14.5
    assert pt.course == 45.0
    assert pt.heading == 46.0
    assert pt.vessel_type == "Tanker"

    traj = AISTrajectory(mmsi=pt.mmsi, vessel_name=pt.vessel_name, points=[pt])
    assert len(traj.points) == 1
    assert traj.interpolated is False


# =============================================================================
# 2. Invalid Coordinates Removal
# =============================================================================
def test_2_invalid_coordinates(analyzer):
    raw_pings = [
        {"mmsi": "111", "timestamp": "2026-08-13T12:00:00Z", "latitude": 56.0, "longitude": 3.0, "speed": 10.0, "course": 0.0},
        {"mmsi": "111", "timestamp": "2026-08-13T12:10:00Z", "latitude": 95.0, "longitude": 3.0, "speed": 10.0, "course": 0.0},  # lat > 90
        {"mmsi": "111", "timestamp": "2026-08-13T12:20:00Z", "latitude": -95.0, "longitude": 3.0, "speed": 10.0, "course": 0.0}, # lat < -90
        {"mmsi": "111", "timestamp": "2026-08-13T12:30:00Z", "latitude": 56.0, "longitude": 185.0, "speed": 10.0, "course": 0.0}, # lon > 180
        {"mmsi": "111", "timestamp": "2026-08-13T12:40:00Z", "latitude": 56.0, "longitude": -195.0, "speed": 10.0, "course": 0.0},# lon < -180
        {"mmsi": "111", "timestamp": "2026-08-13T12:50:00Z", "latitude": 0.0, "longitude": 0.0, "speed": 10.0, "course": 0.0},      # GPS null (0, 0)
        {"mmsi": "111", "timestamp": "2026-08-13T13:00:00Z", "latitude": float("nan"), "longitude": 3.0, "speed": 10.0, "course": 0.0}, # NaN
    ]
    sanitized, raw_count, rejected_count = analyzer.sanitize_pings(raw_pings)
    assert raw_count == 7
    assert len(sanitized) == 1
    assert rejected_count == 6
    assert sanitized[0].latitude == 56.0


# =============================================================================
# 3. Invalid Timestamps Removal
# =============================================================================
def test_3_invalid_timestamps(analyzer):
    raw_pings = [
        {"mmsi": "222", "timestamp": "2026-08-13T12:00:00Z", "latitude": 56.0, "longitude": 3.0, "speed": 10.0, "course": 0.0},
        {"mmsi": "222", "timestamp": "NOT_A_TIMESTAMP", "latitude": 56.0, "longitude": 3.0, "speed": 10.0, "course": 0.0},
        {"mmsi": "222", "timestamp": None, "latitude": 56.0, "longitude": 3.0, "speed": 10.0, "course": 0.0},
        {"mmsi": "222", "timestamp": "", "latitude": 56.0, "longitude": 3.0, "speed": 10.0, "course": 0.0},
    ]
    sanitized, raw_count, rejected_count = analyzer.sanitize_pings(raw_pings)
    assert raw_count == 4
    assert len(sanitized) == 1
    assert rejected_count == 3


# =============================================================================
# 4. Duplicate Positions Removal
# =============================================================================
def test_4_duplicate_positions(analyzer):
    raw_pings = [
        {"mmsi": "333", "timestamp": "2026-08-13T12:00:00Z", "latitude": 56.0, "longitude": 3.0, "speed": 10.0, "course": 0.0},
        {"mmsi": "333", "timestamp": "2026-08-13T12:00:00Z", "latitude": 56.0, "longitude": 3.0, "speed": 10.0, "course": 0.0}, # exact duplicate timestamp dt=0
        {"mmsi": "333", "timestamp": "2026-08-13T12:30:00Z", "latitude": 56.1, "longitude": 3.0, "speed": 10.0, "course": 0.0},
    ]
    sanitized, raw_count, rejected_count = analyzer.sanitize_pings(raw_pings)
    assert raw_count == 3
    assert len(sanitized) == 2
    assert rejected_count == 1


# =============================================================================
# 5. Impossible Speeds & Teleportation Removal
# =============================================================================
def test_5_impossible_speed(analyzer):
    raw_pings = [
        {"mmsi": "444", "timestamp": "2026-08-13T12:00:00Z", "latitude": 56.0, "longitude": 3.0, "speed": 12.0, "course": 0.0},
        {"mmsi": "444", "timestamp": "2026-08-13T12:15:00Z", "latitude": 56.05, "longitude": 3.0, "speed": 85.0, "course": 0.0}, # speed > 60 knots
        {"mmsi": "444", "timestamp": "2026-08-13T12:30:00Z", "latitude": 56.10, "longitude": 3.0, "speed": -2.0, "course": 0.0}, # negative speed
        # Kinematic jump: 120 km in 5 minutes = > 700 knots
        {"mmsi": "444", "timestamp": "2026-08-13T12:05:00Z", "latitude": 57.10, "longitude": 3.0, "speed": 15.0, "course": 0.0},
    ]
    sanitized, raw_count, rejected_count = analyzer.sanitize_pings(raw_pings)
    assert raw_count == 4
    assert len(sanitized) == 1
    assert rejected_count == 3


# =============================================================================
# 6. Chronological Ordering
# =============================================================================
def test_6_chronological_ordering(analyzer):
    # Unsorted raw input
    raw_pings = [
        {"mmsi": "555", "timestamp": "2026-08-13T14:00:00Z", "latitude": 56.2, "longitude": 3.0, "speed": 10.0, "course": 0.0},
        {"mmsi": "555", "timestamp": "2026-08-13T12:00:00Z", "latitude": 56.0, "longitude": 3.0, "speed": 10.0, "course": 0.0},
        {"mmsi": "555", "timestamp": "2026-08-13T13:00:00Z", "latitude": 56.1, "longitude": 3.0, "speed": 10.0, "course": 0.0},
    ]
    sanitized, _, _ = analyzer.sanitize_pings(raw_pings)
    assert len(sanitized) == 3
    assert sanitized[0].timestamp < sanitized[1].timestamp < sanitized[2].timestamp


# =============================================================================
# 7. Trajectory Reconstruction
# =============================================================================
def test_7_trajectory_reconstruction(analyzer):
    pts = [
        AISPoint(mmsi="666", timestamp=datetime(2026, 8, 13, 12, 0, tzinfo=timezone.utc), latitude=56.0, longitude=3.0, speed=10.0, course=45.0, vessel_name="VESSEL A"),
        AISPoint(mmsi="666", timestamp=datetime(2026, 8, 13, 13, 0, tzinfo=timezone.utc), latitude=56.1, longitude=3.1, speed=10.0, course=45.0, vessel_name="VESSEL A"),
        AISPoint(mmsi="777", timestamp=datetime(2026, 8, 13, 12, 30, tzinfo=timezone.utc), latitude=57.0, longitude=4.0, speed=12.0, course=90.0, vessel_name="VESSEL B"),
    ]
    trajs = analyzer.reconstruct_trajectories(pts)
    assert len(trajs) == 2
    mmsis = {t.mmsi for t in trajs}
    assert mmsis == {"666", "777"}
    traj666 = next(t for t in trajs if t.mmsi == "666")
    assert len(traj666.points) == 2
    assert traj666.vessel_name == "VESSEL A"


# =============================================================================
# 8. Temporal Filtering
# =============================================================================
def test_8_temporal_filtering(analyzer, north_sea_source):
    _, centroid, window = north_sea_source
    # Release window: 11:00 - 16:00 UTC. With 3h buffer: 08:00 - 19:00 UTC.

    # Inside window
    t_inside = AISTrajectory(
        mmsi="IN",
        points=[
            AISPoint(mmsi="IN", timestamp=datetime(2026, 8, 13, 13, 0, tzinfo=timezone.utc), latitude=56.32, longitude=3.02, speed=10.0, course=0.0)
        ]
    )
    # Outside window (way earlier)
    t_early = AISTrajectory(
        mmsi="EARLY",
        points=[
            AISPoint(mmsi="EARLY", timestamp=datetime(2026, 8, 13, 2, 0, tzinfo=timezone.utc), latitude=56.32, longitude=3.02, speed=10.0, course=0.0)
        ]
    )
    # Outside window (way later)
    t_late = AISTrajectory(
        mmsi="LATE",
        points=[
            AISPoint(mmsi="LATE", timestamp=datetime(2026, 8, 14, 2, 0, tzinfo=timezone.utc), latitude=56.32, longitude=3.02, speed=10.0, course=0.0)
        ]
    )

    filtered = analyzer.filter_candidates([t_inside, t_early, t_late], centroid, window, spatial_radius_km=30.0)
    assert len(filtered) == 1
    assert filtered[0].mmsi == "IN"


# =============================================================================
# 9. Spatial Filtering
# =============================================================================
def test_9_spatial_filtering(analyzer, north_sea_source):
    _, centroid, window = north_sea_source

    # Close (within 10 km of centroid 56.325°N, 3.020°E)
    t_close = AISTrajectory(
        mmsi="CLOSE",
        points=[
            AISPoint(mmsi="CLOSE", timestamp=datetime(2026, 8, 13, 13, 0, tzinfo=timezone.utc), latitude=56.33, longitude=3.03, speed=10.0, course=0.0)
        ]
    )
    # Far away (> 80 km)
    t_far = AISTrajectory(
        mmsi="FAR",
        points=[
            AISPoint(mmsi="FAR", timestamp=datetime(2026, 8, 13, 13, 0, tzinfo=timezone.utc), latitude=57.20, longitude=3.02, speed=10.0, course=0.0)
        ]
    )

    filtered = analyzer.filter_candidates([t_close, t_far], centroid, window, spatial_radius_km=25.0)
    assert len(filtered) == 1
    assert filtered[0].mmsi == "CLOSE"


# =============================================================================
# 10. Source-Region Intersection (Polygon & Line Segments)
# =============================================================================
def test_10_source_region_intersection(analyzer):
    # Square polygon [0, 2] x [0, 2] in lon, lat
    poly_ring = [
        [0.0, 0.0],
        [2.0, 0.0],
        [2.0, 2.0],
        [0.0, 2.0],
        [0.0, 0.0],
    ]

    # Trajectory 1: ping strictly inside polygon
    t1 = AISTrajectory(
        mmsi="INSIDE",
        points=[AISPoint(mmsi="INSIDE", timestamp=datetime(2026, 8, 13, 12, 0, tzinfo=timezone.utc), latitude=1.0, longitude=1.0, speed=10.0, course=0.0)]
    )
    assert analyzer.check_source_region_intersection(t1, poly_ring) is True

    # Trajectory 2: pings outside, but line segment cuts straight through polygon
    t2 = AISTrajectory(
        mmsi="CUTS_THROUGH",
        points=[
            AISPoint(mmsi="CUTS_THROUGH", timestamp=datetime(2026, 8, 13, 12, 0, tzinfo=timezone.utc), latitude=1.0, longitude=-1.0, speed=10.0, course=90.0),
            AISPoint(mmsi="CUTS_THROUGH", timestamp=datetime(2026, 8, 13, 13, 0, tzinfo=timezone.utc), latitude=1.0, longitude=3.0, speed=10.0, course=90.0),
        ]
    )
    assert analyzer.check_source_region_intersection(t2, poly_ring) is True

    # Trajectory 3: stays completely outside
    t3 = AISTrajectory(
        mmsi="OUTSIDE",
        points=[
            AISPoint(mmsi="OUTSIDE", timestamp=datetime(2026, 8, 13, 12, 0, tzinfo=timezone.utc), latitude=5.0, longitude=5.0, speed=10.0, course=0.0),
            AISPoint(mmsi="OUTSIDE", timestamp=datetime(2026, 8, 13, 13, 0, tzinfo=timezone.utc), latitude=5.5, longitude=5.0, speed=10.0, course=0.0),
        ]
    )
    assert analyzer.check_source_region_intersection(t3, poly_ring) is False


# =============================================================================
# 11. Minimum Distance / Closest Point of Approach (CPA)
# =============================================================================
def test_11_minimum_distance_cpa(analyzer):
    centroid = CoordinatePoint(latitude=56.0000, longitude=3.0000)
    traj = AISTrajectory(
        mmsi="CPA_TEST",
        points=[
            AISPoint(mmsi="CPA_TEST", timestamp=datetime(2026, 8, 13, 12, 0, tzinfo=timezone.utc), latitude=55.80, longitude=3.00, speed=12.0, course=0.0),
            AISPoint(mmsi="CPA_TEST", timestamp=datetime(2026, 8, 13, 13, 0, tzinfo=timezone.utc), latitude=56.02, longitude=3.00, speed=12.0, course=0.0),  # closest
            AISPoint(mmsi="CPA_TEST", timestamp=datetime(2026, 8, 13, 14, 0, tzinfo=timezone.utc), latitude=56.30, longitude=3.00, speed=12.0, course=0.0),
        ]
    )
    cpa_pt, min_dist, cpa_time, cpa_idx = analyzer.compute_cpa(traj, centroid)
    assert cpa_idx == 1
    assert cpa_pt.latitude == 56.02
    assert cpa_time == datetime(2026, 8, 13, 13, 0, tzinfo=timezone.utc)
    assert 2.0 <= min_dist <= 2.5  # 0.02 deg lat ~ 2.22 km


# =============================================================================
# 12. AIS Gap Detection (Non-Accusatory)
# =============================================================================
def test_12_ais_gap_detection(analyzer, north_sea_source):
    _, _, window = north_sea_source
    # Gap of 2.5 hours overlapping the release window
    pts = [
        AISPoint(mmsi="GAP_SHIP", timestamp=datetime(2026, 8, 13, 12, 0, tzinfo=timezone.utc), latitude=56.3, longitude=3.0, speed=10.0, course=0.0),
        AISPoint(mmsi="GAP_SHIP", timestamp=datetime(2026, 8, 13, 14, 30, tzinfo=timezone.utc), latitude=56.35, longitude=3.0, speed=10.0, course=0.0),
    ]
    traj = AISTrajectory(mmsi="GAP_SHIP", points=pts)
    gap = analyzer.detect_ais_gaps(traj, window)
    assert gap.detected is True
    assert gap.gap_duration_minutes == 150.0
    # Verifying non-accusatory terminology
    assert "transponder silence" in gap.description.lower()
    assert "guilt" not in gap.description.lower()


# =============================================================================
# 13. Synthetic Scenario: Vessel A (Candidate), Vessel B (Far), Vessel C (Late)
# =============================================================================
def test_13_synthetic_scenario_known_vessels(analyzer, north_sea_source):
    source_geom, centroid, window = north_sea_source
    # Release window: 11:00 - 16:00 UTC. Source centroid: (56.325°N, 3.020°E)

    raw_pings = [
        # Vessel A: Tanker passing through source region during release window
        {"mmsi": "A_CANDIDATE", "VesselName": "VESSEL ALPHA", "VesselType": "Tanker", "timestamp": "2026-08-13T13:00:00Z", "latitude": 56.324, "longitude": 3.019, "speed": 11.0, "course": 45.0},
        {"mmsi": "A_CANDIDATE", "VesselName": "VESSEL ALPHA", "VesselType": "Tanker", "timestamp": "2026-08-13T13:30:00Z", "latitude": 56.326, "longitude": 3.021, "speed": 10.5, "course": 45.0},

        # Vessel B: Cargo passing 75 km south during release window
        {"mmsi": "B_FAR", "VesselName": "VESSEL BETA", "VesselType": "Cargo", "timestamp": "2026-08-13T13:00:00Z", "latitude": 55.65, "longitude": 3.020, "speed": 16.0, "course": 90.0},
        {"mmsi": "B_FAR", "VesselName": "VESSEL BETA", "VesselType": "Cargo", "timestamp": "2026-08-13T13:30:00Z", "latitude": 55.65, "longitude": 3.200, "speed": 16.0, "course": 90.0},

        # Vessel C: Container passing through source region 18 hours later (Aug 14 at 08:00)
        {"mmsi": "C_LATE", "VesselName": "VESSEL GAMMA", "VesselType": "Container", "timestamp": "2026-08-14T08:00:00Z", "latitude": 56.325, "longitude": 3.020, "speed": 18.0, "course": 45.0},
        {"mmsi": "C_LATE", "VesselName": "VESSEL GAMMA", "VesselType": "Container", "timestamp": "2026-08-14T08:30:00Z", "latitude": 56.330, "longitude": 3.025, "speed": 18.0, "course": 45.0},
    ]

    candidates = analyzer.analyze_candidates(
        probable_source_region=source_geom,
        release_time_window=window,
        spatial_radius_km=25.0,
        ais_dataset=raw_pings,
        source_centroid=centroid,
    )

    # STRICT EVALUATION: Only Vessel A becomes a candidate!
    candidate_mmsis = [c.mmsi for c in candidates]
    assert "A_CANDIDATE" in candidate_mmsis
    assert "B_FAR" not in candidate_mmsis
    assert "C_LATE" not in candidate_mmsis
    assert len(candidates) == 1

    cand_a = candidates[0]
    assert cand_a.mmsi == "A_CANDIDATE"
    assert cand_a.vessel_name == "VESSEL ALPHA"
    assert cand_a.temporal_match is True
    assert cand_a.spatial_match is True
    assert cand_a.passed_through_source_region is True
    assert cand_a.entered_source_region is True
    assert cand_a.closest_distance_km < 1.0
    assert cand_a.candidate_status == "Candidate"


# =============================================================================
# 14. No Candidate Scenario (Empty Result Handled Gracefully)
# =============================================================================
def test_14_no_candidate_scenario(analyzer, north_sea_source):
    source_geom, centroid, window = north_sea_source

    # Raw pings of vessels nowhere near North Sea source region
    raw_pings = [
        {"mmsi": "PACIFIC_SHIP", "timestamp": "2026-08-13T13:00:00Z", "latitude": 10.0, "longitude": 120.0, "speed": 12.0, "course": 0.0},
    ]

    candidates = analyzer.analyze_candidates(
        probable_source_region=source_geom,
        release_time_window=window,
        spatial_radius_km=25.0,
        ais_dataset=raw_pings,
        source_centroid=centroid,
    )
    assert isinstance(candidates, list)
    assert len(candidates) == 0


# =============================================================================
# 15. Historical Timestamp Handling (Uses 2026 Historical Dates, Not Current Time)
# =============================================================================
def test_15_historical_timestamp_handling(analyzer, north_sea_source):
    source_geom, centroid, window = north_sea_source
    assert window.earliest.year == 2026

    raw_pings = [
        {"mmsi": "HIST_1", "timestamp": "2026-08-13T13:00:00Z", "latitude": 56.325, "longitude": 3.020, "speed": 10.0, "course": 0.0}
    ]
    candidates = analyzer.analyze_candidates(
        probable_source_region=source_geom,
        release_time_window=window,
        spatial_radius_km=25.0,
        ais_dataset=raw_pings,
        source_centroid=centroid,
    )
    assert len(candidates) == 1
    assert candidates[0].time_of_closest_approach.year == 2026


# =============================================================================
# 16. Demo Mode Isolation & Deterministic Fixture
# =============================================================================
def test_16_demo_mode_isolation(analyzer, north_sea_source):
    source_geom, centroid, window = north_sea_source

    # In DEMO mode, passing ais_dataset=None automatically loads the indexed deterministic fixture
    candidates = analyzer.analyze_candidates(
        probable_source_region=source_geom,
        release_time_window=window,
        spatial_radius_km=30.0,
        ais_dataset=None,
        source_centroid=centroid,
        app_mode="DEMO",
    )
    assert len(candidates) >= 1
    # Nordic Titan should be top candidate
    assert candidates[0].mmsi == "244123456"
    assert candidates[0].vessel_name == "MT NORDIC TITAN"


# =============================================================================
# 17. Real Data Mode Data Integrity (No Silent Mock Data)
# =============================================================================
def test_17_real_data_mode_data_integrity(analyzer, north_sea_source):
    source_geom, centroid, window = north_sea_source

    # In REAL mode, if no dataset or GFW credentials are provided,
    # the analyzer MUST NOT silently substitute fixture data!
    with pytest.raises(ValueError, match="REAL mode requires an AIS dataset or valid GFW_API_TOKEN"):
        analyzer.analyze_candidates(
            probable_source_region=source_geom,
            release_time_window=window,
            spatial_radius_km=30.0,
            ais_dataset=None,
            source_centroid=centroid,
            app_mode="REAL",
        )


# =============================================================================
# 18. API Endpoint End-to-End Verification
# =============================================================================
def test_18_api_ais_analyze_candidates_endpoint(north_sea_source):
    source_geom, centroid, window = north_sea_source
    fixture_path = str(Path(__file__).resolve().parent / "fixtures" / "marine_cadastre_ais_fixture.csv")

    client = TestClient(app)
    payload = {
        "probable_source_region": source_geom.model_dump(),
        "source_centroid": centroid.model_dump(),
        "release_time_window": window.model_dump(mode="json"),
        "spatial_radius_km": 30.0,
        "ais_dataset_path": fixture_path,
        "app_mode": "DEMO",
    }

    response = client.post("/api/ais/analyze-candidates", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0

    top = data[0]
    assert top["mmsi"] == "244123456"
    assert top["vessel_name"] == "MT NORDIC TITAN"
    assert top["temporal_match"] is True
    assert top["spatial_match"] is True
    assert "min_distance_km" in top
    assert "entered_source_region" in top
    assert "trajectory_quality" in top
    assert "ais_gap_detected" in top
    assert top["candidate_status"] == "Candidate"

    # Verify no culpability or guilt claims exist in response
    assert "is_guilty" not in top
    assert "culprit" not in top
    assert "responsible" not in top
