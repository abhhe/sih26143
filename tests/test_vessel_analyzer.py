import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path

from backend.app.domain.models import (
    AISPoint,
    AISTrajectory,
    CoordinatePoint,
    SpillGeometry,
    ReleaseTimeWindow,
    CandidateVesselFeatures,
)
from backend.app.adapters.ais.vessel_analyzer import (
    AISVesselAnalyzer,
    haversine_distance_km,
    calculate_bearing_deg,
    angular_difference_deg,
    point_in_polygon,
    segments_intersect,
)


@pytest.fixture
def analyzer():
    return AISVesselAnalyzer()


@pytest.fixture
def sample_source():
    # Probable source region near North Sea 56.32°N, 3.02°E
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
        earliest=datetime(2026, 8, 13, 12, 0, 0, tzinfo=timezone.utc),
        latest=datetime(2026, 8, 13, 16, 0, 0, tzinfo=timezone.utc),
        most_probable=datetime(2026, 8, 13, 14, 0, 0, tzinfo=timezone.utc),
        slick_age_hours_range=(14.0, 18.0),
    )
    return source_geom, centroid, window


def test_haversine_and_bearing_accuracy():
    # Equator 1 degree longitude ~ 111.32 km
    d = haversine_distance_km(0.0, 0.0, 0.0, 1.0)
    assert 111.0 <= d <= 111.5

    # Heading straight North: 0 deg
    bearing_north = calculate_bearing_deg(0.0, 0.0, 1.0, 0.0)
    assert bearing_north == 0.0

    # Heading straight East: 90 deg
    bearing_east = calculate_bearing_deg(0.0, 0.0, 0.0, 1.0)
    assert bearing_east == 90.0

    # Heading straight South: 180 deg
    bearing_south = calculate_bearing_deg(1.0, 0.0, 0.0, 0.0)
    assert bearing_south == 180.0

    # Angular difference across 360 boundary
    diff = angular_difference_deg(355.0, 5.0)
    assert diff == 10.0


def test_point_in_polygon_and_segment_intersection():
    poly = [
        [0.0, 0.0],
        [2.0, 0.0],
        [2.0, 2.0],
        [0.0, 2.0],
        [0.0, 0.0],
    ]
    # Inside
    assert point_in_polygon(1.0, 1.0, poly) is True
    # Outside
    assert point_in_polygon(3.0, 3.0, poly) is False
    assert point_in_polygon(-0.5, 1.0, poly) is False

    # Segment crossing
    p1 = (-1.0, 1.0)
    p2 = (3.0, 1.0)
    p3 = (0.0, 0.0)
    p4 = (0.0, 2.0)
    assert segments_intersect(p1, p2, p3, p4) is True


def test_timestamp_normalization(analyzer):
    # ISO string with Z
    dt_z = analyzer.normalize_timestamp("2026-08-13T12:00:00Z")
    assert dt_z == datetime(2026, 8, 13, 12, 0, 0, tzinfo=timezone.utc)

    # ISO string with offset
    dt_off = analyzer.normalize_timestamp("2026-08-13 14:00:00+02:00")
    assert dt_off == datetime(2026, 8, 13, 12, 0, 0, tzinfo=timezone.utc)

    # Epoch timestamp
    dt_epoch = analyzer.normalize_timestamp(1786622400)
    assert dt_epoch.tzinfo == timezone.utc

    # Naive datetime gets converted to UTC
    naive = datetime(2026, 8, 13, 12, 0, 0)
    dt_naive = analyzer.normalize_timestamp(naive)
    assert dt_naive.tzinfo == timezone.utc


def test_sanitize_pings_invalid_coordinates(analyzer):
    raw_pings = [
        # Valid ping
        {"mmsi": "123456789", "timestamp": "2026-08-13T12:00:00Z", "latitude": 56.3, "longitude": 3.0, "speed": 12.0, "course": 45.0},
        # Invalid latitude (> 90)
        {"mmsi": "123456789", "timestamp": "2026-08-13T12:10:00Z", "latitude": 95.0, "longitude": 3.0, "speed": 12.0, "course": 45.0},
        # Invalid longitude (< -180)
        {"mmsi": "123456789", "timestamp": "2026-08-13T12:20:00Z", "latitude": 56.3, "longitude": -190.0, "speed": 12.0, "course": 45.0},
        # GPS Null (0, 0)
        {"mmsi": "123456789", "timestamp": "2026-08-13T12:30:00Z", "latitude": 0.0, "longitude": 0.0, "speed": 12.0, "course": 45.0},
        # NaN coordinates
        {"mmsi": "123456789", "timestamp": "2026-08-13T12:40:00Z", "latitude": float("nan"), "longitude": 3.0, "speed": 12.0, "course": 45.0},
    ]

    sanitized, raw_count, rejected_count = analyzer.sanitize_pings(raw_pings)
    assert raw_count == 5
    assert len(sanitized) == 1
    assert rejected_count == 4
    assert sanitized[0].latitude == 56.3


def test_sanitize_pings_impossible_speeds(analyzer):
    raw_pings = [
        # Valid ping
        {"mmsi": "111222333", "timestamp": "2026-08-13T12:00:00Z", "latitude": 56.0, "longitude": 3.0, "speed": 14.0, "course": 90.0},
        # SOG > 60 knots
        {"mmsi": "111222333", "timestamp": "2026-08-13T12:15:00Z", "latitude": 56.0, "longitude": 3.1, "speed": 75.0, "course": 90.0},
        # Negative speed
        {"mmsi": "111222333", "timestamp": "2026-08-13T12:30:00Z", "latitude": 56.0, "longitude": 3.2, "speed": -5.0, "course": 90.0},
        # Kinematic teleportation jump (teleporting 100 km in 5 minutes = >600 knots)
        {"mmsi": "111222333", "timestamp": "2026-08-13T12:05:00Z", "latitude": 57.0, "longitude": 3.0, "speed": 15.0, "course": 90.0},
    ]

    sanitized, raw_count, rejected_count = analyzer.sanitize_pings(raw_pings)
    assert raw_count == 4
    assert len(sanitized) == 1
    assert rejected_count == 3
    assert sanitized[0].speed == 14.0


def test_reconstruct_trajectories_sorting_and_gaps(analyzer):
    pts = [
        AISPoint(mmsi="999888777", timestamp=datetime(2026, 8, 13, 14, 0, 0, tzinfo=timezone.utc), latitude=56.2, longitude=3.0, speed=10.0, course=0.0),
        AISPoint(mmsi="999888777", timestamp=datetime(2026, 8, 13, 12, 0, 0, tzinfo=timezone.utc), latitude=56.0, longitude=3.0, speed=10.0, course=0.0),
        # Gap of 2.5 hours > 1 hour threshold
        AISPoint(mmsi="999888777", timestamp=datetime(2026, 8, 13, 16, 30, 0, tzinfo=timezone.utc), latitude=56.5, longitude=3.0, speed=10.0, course=0.0),
    ]

    trajs = analyzer.reconstruct_trajectories(pts)
    assert len(trajs) == 1
    traj = trajs[0]
    assert traj.points[0].timestamp < traj.points[1].timestamp < traj.points[2].timestamp
    assert traj.data_gaps_count >= 1


def test_cpa_and_dwell_time(analyzer):
    source_centroid = CoordinatePoint(latitude=56.3000, longitude=3.0000)
    pts = [
        AISPoint(mmsi="123", timestamp=datetime(2026, 8, 13, 12, 0, 0, tzinfo=timezone.utc), latitude=56.2000, longitude=3.0000, speed=12.0, course=0.0),
        AISPoint(mmsi="123", timestamp=datetime(2026, 8, 13, 13, 0, 0, tzinfo=timezone.utc), latitude=56.2950, longitude=3.0000, speed=12.0, course=0.0), # closest
        AISPoint(mmsi="123", timestamp=datetime(2026, 8, 13, 14, 0, 0, tzinfo=timezone.utc), latitude=56.4000, longitude=3.0000, speed=12.0, course=0.0),
    ]
    traj = AISTrajectory(mmsi="123", points=pts)

    closest_pt, min_dist, cpa_time, cpa_idx = analyzer.compute_cpa(traj, source_centroid)
    assert cpa_idx == 1
    assert closest_pt.latitude == 56.2950
    assert min_dist < 1.0  # Approx 0.55 km
    assert cpa_time == datetime(2026, 8, 13, 13, 0, 0, tzinfo=timezone.utc)

    # Test dwell time inside 15 km
    entry_t, exit_t, dwell = analyzer.compute_entry_exit_and_dwell(traj, source_centroid, spatial_radius_km=15.0)
    assert entry_t is not None
    assert exit_t is not None
    assert dwell >= 0.0


def test_route_deviation_detection(analyzer):
    # Case A: Steady transit (MV Pacific Trader style)
    steady_pts = [
        AISPoint(mmsi="101", timestamp=datetime(2026, 8, 13, 9, 0, tzinfo=timezone.utc), latitude=56.0, longitude=3.0, speed=18.5, course=88.0),
        AISPoint(mmsi="101", timestamp=datetime(2026, 8, 13, 9, 30, tzinfo=timezone.utc), latitude=56.0, longitude=3.2, speed=18.6, course=88.0),
        AISPoint(mmsi="101", timestamp=datetime(2026, 8, 13, 10, 0, tzinfo=timezone.utc), latitude=56.0, longitude=3.4, speed=18.4, course=88.0),
    ]
    steady_traj = AISTrajectory(mmsi="101", points=steady_pts)
    spd_steady = analyzer.compute_speed_statistics(steady_traj, cpa_idx=1)
    crs_steady = analyzer.compute_course_statistics(steady_traj)
    dev_steady = analyzer.detect_route_deviation(steady_traj, 1, spd_steady, crs_steady)
    assert dev_steady.detected is False

    # Case B: Speed drop deceleration at CPA (MT Nordic Titan style: 14 kn -> 9.1 kn)
    decel_pts = [
        AISPoint(mmsi="202", timestamp=datetime(2026, 8, 13, 12, 0, tzinfo=timezone.utc), latitude=56.28, longitude=2.95, speed=14.2, course=42.0),
        AISPoint(mmsi="202", timestamp=datetime(2026, 8, 13, 13, 0, tzinfo=timezone.utc), latitude=56.30, longitude=2.98, speed=13.8, course=44.0),
        AISPoint(mmsi="202", timestamp=datetime(2026, 8, 13, 14, 12, tzinfo=timezone.utc), latitude=56.32, longitude=3.02, speed=9.1, course=45.0), # speed drop
        AISPoint(mmsi="202", timestamp=datetime(2026, 8, 13, 15, 30, tzinfo=timezone.utc), latitude=56.36, longitude=3.07, speed=14.0, course=46.0),
    ]
    decel_traj = AISTrajectory(mmsi="202", points=decel_pts)
    spd_decel = analyzer.compute_speed_statistics(decel_traj, cpa_idx=2)
    crs_decel = analyzer.compute_course_statistics(decel_traj)
    dev_decel = analyzer.detect_route_deviation(decel_traj, 2, spd_decel, crs_decel)
    assert dev_decel.detected is True
    assert dev_decel.deviation_type in ("SPEED_DECELERATION", "SHARP_COURSE_CHANGE")

    # Case C: Loitering vessel (Fishing vessel engaged in slow operations)
    loiter_pts = [
        AISPoint(mmsi="303", timestamp=datetime(2026, 8, 13, 12, 0, tzinfo=timezone.utc), latitude=56.12, longitude=3.22, speed=2.5, course=160.0),
        AISPoint(mmsi="303", timestamp=datetime(2026, 8, 13, 13, 0, tzinfo=timezone.utc), latitude=56.13, longitude=3.24, speed=2.8, course=165.0),
        AISPoint(mmsi="303", timestamp=datetime(2026, 8, 13, 14, 0, tzinfo=timezone.utc), latitude=56.14, longitude=3.26, speed=2.6, course=170.0),
    ]
    loiter_traj = AISTrajectory(mmsi="303", points=loiter_pts)
    spd_loiter = analyzer.compute_speed_statistics(loiter_traj, cpa_idx=1)
    crs_loiter = analyzer.compute_course_statistics(loiter_traj)
    dev_loiter = analyzer.detect_route_deviation(loiter_traj, 1, spd_loiter, crs_loiter)
    assert dev_loiter.detected is True
    assert dev_loiter.deviation_type == "LOITERING"


def test_end_to_end_analyze_candidates(analyzer, sample_source):
    source_geom, _, window = sample_source
    fixture_path = Path(__file__).resolve().parent / "fixtures" / "marine_cadastre_ais_fixture.csv"

    # Analyze with 30 km spatial radius
    candidates = analyzer.analyze_candidates(
        probable_source_region=source_geom,
        release_time_window=window,
        spatial_radius_km=30.0,
        ais_dataset=fixture_path,
    )

    assert len(candidates) > 0

    # Ensure output type is strictly CandidateVesselFeatures
    for cand in candidates:
        assert isinstance(cand, CandidateVesselFeatures)
        assert cand.mmsi in ("244123456", "311987654", "219654321")
        assert cand.closest_distance_km >= 0.0
        assert cand.closest_point_to_source.latitude != 0.0
        assert cand.time_of_closest_approach is not None
        assert 0.0 <= cand.approach_direction_deg < 360.0
        assert 0.0 <= cand.departure_direction_deg < 360.0
        assert cand.speed_statistics.mean_speed_knots > 0.0
        assert cand.course_statistics.mean_course_deg >= 0.0

    # MT Nordic Titan (244123456) passed closest to source (56.326°N, 3.021°E vs 56.325°N, 3.020°E)
    top_cand = candidates[0]
    assert top_cand.mmsi == "244123456"
    assert top_cand.vessel_name == "MT NORDIC TITAN"
    assert top_cand.closest_distance_km < 3.0
    assert top_cand.passed_through_source_region is True
    assert top_cand.route_deviation.detected is True
    assert top_cand.speed_statistics.speed_drop_knots > 4.0

    # Pacific Trader was further north
    mmsis = [c.mmsi for c in candidates]
    assert "311987654" in mmsis

    # Scientific principle: Candidate output has NO guilt or culpability attribute
    for cand in candidates:
        assert not hasattr(cand, "is_guilty")
        assert not hasattr(cand, "responsible")
        assert not hasattr(cand, "culpability_score")


def test_api_ais_analyze_candidates_endpoint(sample_source):
    from fastapi.testclient import TestClient
    from backend.app.main import app

    source_geom, centroid, window = sample_source
    fixture_path = str(Path(__file__).resolve().parent / "fixtures" / "marine_cadastre_ais_fixture.csv")

    client = TestClient(app)
    payload = {
        "probable_source_region": source_geom.model_dump(),
        "source_centroid": centroid.model_dump(),
        "release_time_window": window.model_dump(mode="json"),
        "spatial_radius_km": 30.0,
        "ais_dataset_path": fixture_path,
    }

    response = client.post("/api/ais/analyze-candidates", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert data[0]["mmsi"] == "244123456"
    assert "closest_point_to_source" in data[0]
    assert "speed_statistics" in data[0]
    assert "course_statistics" in data[0]
    assert "route_deviation" in data[0]

