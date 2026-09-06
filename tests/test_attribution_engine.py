# pyrefly: ignore [missing-import]
import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
# pyrefly: ignore [missing-import]
from fastapi.testclient import TestClient

from backend.app.domain.models import (
    SpillDetection,
    SpillGeometry,
    CoordinatePoint,
    BoundingBox,
    ReleaseTimeWindow,
    DriftUncertainty,
    DriftResult,
    ParticleStep,
    ParticleTrajectory,
    EvidenceClassification,
    VesselEvidence,
)
from backend.app.adapters.attribution.attribution_engine import ExplainableAttributionEngine
from backend.app.main import app


@pytest.fixture
def sample_attribution_context():
    """Build synthetic North Sea oil spill, drift result, and release window."""
    # 1. Spill Detection
    spill = SpillDetection(
        detected=True,
        confidence=0.92,
        centroid=CoordinatePoint(latitude=56.4500, longitude=3.2000),
        bounding_box=BoundingBox(
            min_latitude=56.4300, min_longitude=3.1700,
            max_latitude=56.4700, max_longitude=3.2300,
        ),
        area=12.4,
        perimeter=18.6,
        orientation=45.0,
        spill_mask=SpillGeometry(
            type="Polygon",
            coordinates=[[[3.17, 56.43], [3.23, 56.43], [3.23, 56.47], [3.17, 56.47], [3.17, 56.43]]],
        ),
    )

    # 2. Source Region & Centroid (near 56.325°N, 3.020°E)
    source_poly = [
        [3.0000, 56.3100],
        [3.0400, 56.3100],
        [3.0400, 56.3400],
        [3.0000, 56.3400],
        [3.0000, 56.3100],
    ]
    source_centroid = CoordinatePoint(latitude=56.3250, longitude=3.0200)

    # 3. Release Time Window (12:00 to 16:00 UTC, peak 14:00 UTC)
    release_window = ReleaseTimeWindow(
        earliest=datetime(2026, 8, 13, 12, 0, 0, tzinfo=timezone.utc),
        latest=datetime(2026, 8, 13, 16, 0, 0, tzinfo=timezone.utc),
        most_probable=datetime(2026, 8, 13, 14, 0, 0, tzinfo=timezone.utc),
        slick_age_hours_range=(14.0, 18.0),
    )

    # 4. Monte Carlo Particle Trajectories
    particles = []
    for pid in range(50):
        # advecting from (56.45, 3.20) back towards (56.325, 3.02)
        steps = [
            ParticleStep(particle_id=pid, timestamp=datetime(2026, 8, 14, 6, 0, tzinfo=timezone.utc), latitude=56.45, longitude=3.20),
            ParticleStep(particle_id=pid, timestamp=datetime(2026, 8, 13, 14, 0, tzinfo=timezone.utc), latitude=56.325 + (pid * 0.0002), longitude=3.020 + (pid * 0.0002)),
        ]
        particles.append(ParticleTrajectory(particle_id=pid, steps=steps))

    uncertainty = DriftUncertainty(
        spatial_radius_km=10.0,
        major_semi_axis_km=12.0,
        minor_semi_axis_km=8.0,
        diffusion_coefficient=5.0,
        confidence_level=0.95,
    )

    drift_result = DriftResult(
        particle_trajectories=particles,
        source_region=SpillGeometry(type="Polygon", coordinates=[source_poly]),
        source_centroid=source_centroid,
        uncertainty=uncertainty,
        release_time_window=release_window,
        drift_duration_hours=16.0,
        particle_count=len(particles),
    )

    fixture_csv = Path(__file__).resolve().parent / "fixtures" / "marine_cadastre_ais_fixture.csv"
    return spill, drift_result, fixture_csv


@pytest.mark.asyncio
async def test_attribution_scoring_strong_candidate(sample_attribution_context):
    spill, drift_result, fixture_csv = sample_attribution_context
    engine = ExplainableAttributionEngine()

    candidates, top_cand, reason = await engine.evaluate_candidates(
        spill=spill,
        drift_result=drift_result,
        candidate_trajectories=fixture_csv,
        evidence_threshold=50.0,
    )

    assert reason is None
    assert top_cand is not None
    assert len(candidates) >= 2

    # MT Nordic Titan (244123456) must be rank 1 Strong Candidate
    assert top_cand.mmsi == "244123456"
    assert top_cand.rank == 1
    assert top_cand.vessel_name == "MT NORDIC TITAN"
    assert top_cand.overall_evidence_score >= 80.0
    assert top_cand.classification == EvidenceClassification.STRONG_CANDIDATE

    # Verify component scores
    assert top_cand.spatial_score >= 85.0
    assert top_cand.temporal_score >= 80.0
    assert top_cand.trajectory_score >= 80.0
    assert top_cand.behavioral_score >= 50.0
    assert "spatial" in top_cand.component_scores

    # Verify explainability and limitations
    assert len(top_cand.explanation) >= 2
    assert len(top_cand.limitations) >= 2
    assert top_cand.counterfactual_explanation is not None


@pytest.mark.asyncio
async def test_attribution_ranking_hierarchy(sample_attribution_context):
    spill, drift_result, fixture_csv = sample_attribution_context
    engine = ExplainableAttributionEngine()

    candidates, top_cand, _ = await engine.evaluate_candidates(
        spill=spill,
        drift_result=drift_result,
        candidate_trajectories=fixture_csv,
        evidence_threshold=30.0,
    )

    # Verify strictly decreasing score order and proper rank indexing
    scores = [c.overall_evidence_score for c in candidates]
    assert scores == sorted(scores, reverse=True)
    for idx, c in enumerate(candidates):
        assert c.rank == idx + 1

    # MV Pacific Trader (Cargo) passed earlier and further north -> lower rank than tanker
    mmsi_list = [c.mmsi for c in candidates]
    assert mmsi_list.index("244123456") < mmsi_list.index("311987654")


@pytest.mark.asyncio
async def test_insufficient_evidence_fail_safe(sample_attribution_context):
    spill, drift_result, fixture_csv = sample_attribution_context

    # Case A: Shifted release window where candidates are far outside temporal window (3 days prior)
    unmatched_drift = drift_result.model_copy(deep=True)
    unmatched_drift.release_time_window = ReleaseTimeWindow(
        earliest=datetime(2026, 8, 10, 12, 0, 0, tzinfo=timezone.utc),
        latest=datetime(2026, 8, 10, 16, 0, 0, tzinfo=timezone.utc),
        most_probable=datetime(2026, 8, 10, 14, 0, 0, tzinfo=timezone.utc),
        slick_age_hours_range=(84.0, 88.0),
    )

    engine = ExplainableAttributionEngine(min_evidence_threshold=50.0)

    candidates, top_cand, reason = await engine.evaluate_candidates(
        spill=spill,
        drift_result=unmatched_drift,
        candidate_trajectories=fixture_csv,
        evidence_threshold=50.0,
    )

    # Neither vessel matches temporal release window -> zero candidates pass corridor filter
    assert top_cand is None
    assert reason is not None
    assert reason.startswith("INSUFFICIENT EVIDENCE: Zero candidate vessels")

    # Case B: Standard drift result with threshold set above top candidate score (100.0)
    candidates_strict, top_cand_strict, reason_strict = await engine.evaluate_candidates(
        spill=spill,
        drift_result=drift_result,
        candidate_trajectories=fixture_csv,
        evidence_threshold=100.0,
    )
    assert len(candidates_strict) >= 2
    assert top_cand_strict is None
    assert reason_strict is not None
    assert reason_strict.startswith("INSUFFICIENT EVIDENCE: No candidate vessel reached the minimum evidence threshold")




@pytest.mark.asyncio
async def test_counterfactual_explanation_content(sample_attribution_context):
    spill, drift_result, fixture_csv = sample_attribution_context
    engine = ExplainableAttributionEngine()

    candidates, _, _ = await engine.evaluate_candidates(
        spill=spill,
        drift_result=drift_result,
        candidate_trajectories=fixture_csv,
        evidence_threshold=30.0,
    )

    # Find the lower-scoring candidate (MV Pacific Trader or FV Sea Hunter)
    lower_cand = candidates[-1]
    assert lower_cand.counterfactual_explanation is not None
    assert "Candidate ranking decreased because" in lower_cand.counterfactual_explanation


@pytest.mark.asyncio
async def test_custom_configurable_weights(sample_attribution_context):
    spill, drift_result, fixture_csv = sample_attribution_context

    # Weighting emphasizing purely spatial (80%) and temporal (20%)
    custom_engine = ExplainableAttributionEngine(
        spatial_weight=80.0,
        temporal_weight=20.0,
        trajectory_weight=0.0,
        drift_weight=0.0,
        behavioral_weight=0.0,
    )

    candidates, top_cand, _ = await custom_engine.evaluate_candidates(
        spill=spill,
        drift_result=drift_result,
        candidate_trajectories=fixture_csv,
    )

    assert top_cand is not None
    assert top_cand.scoring_weights_used["spatial"] == 80.0
    assert top_cand.scoring_weights_used["behavioral"] == 0.0


def test_api_attribution_evaluate_endpoint(sample_attribution_context):
    spill, drift_result, fixture_csv = sample_attribution_context
    client = TestClient(app)

    payload = {
        "spill": spill.model_dump(),
        "drift_result": drift_result.model_dump(mode="json"),
        "ais_dataset_path": str(fixture_csv),
        "evidence_threshold": 50.0,
    }

    response = client.post("/api/attribution/evaluate", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert "candidates" in data
    assert len(data["candidates"]) >= 2
    assert data["top_candidate"] is not None
    assert data["top_candidate"]["mmsi"] == "244123456"
    assert data["top_candidate"]["classification"] == "Strong Candidate"
    assert "component_scores" in data["top_candidate"]
    assert "counterfactual_explanation" in data["top_candidate"]
