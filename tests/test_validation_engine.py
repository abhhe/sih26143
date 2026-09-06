import pytest
from fastapi.testclient import TestClient
from backend.app.adapters.validation.benchmark_validator import SyntheticBenchmarkValidator
from backend.app.main import app


def test_synthetic_scenario_generation():
    validator = SyntheticBenchmarkValidator()
    scenario = validator.generate_controlled_scenario()

    assert "spill" in scenario
    assert scenario["spill"].detected is True
    assert scenario["obs_lat"] > scenario["gt_source_lat"]
    assert scenario["obs_time"] > scenario["gt_release_time"]


def test_evaluate_benchmark_metrics():
    validator = SyntheticBenchmarkValidator()
    metrics = validator.evaluate_benchmark(num_runs=15)

    assert metrics.source_localization_error_km > 0.0
    assert metrics.source_localization_error_km < 5.0
    assert metrics.release_time_error_hours >= 0.0
    assert metrics.top1_accuracy_pct >= 85.0
    assert metrics.top3_accuracy_pct >= 95.0
    assert len(metrics.sensitivity_matrix) >= 5
    assert "controlled/synthetic" in metrics.disclaimer.lower()


def test_api_validation_endpoints():
    client = TestClient(app)

    # Test GET /api/validation/metrics
    res_get = client.get("/api/validation/metrics")
    assert res_get.status_code == 200
    data_get = res_get.json()
    assert "source_localization_error_km" in data_get
    assert "top1_accuracy_pct" in data_get
    assert len(data_get["sensitivity_matrix"]) > 0

    # Test POST /api/validation/run
    res_post = client.post("/api/validation/run?num_runs=10")
    assert res_post.status_code == 200
    data_post = res_post.json()
    assert data_post["scenarios_evaluated"] == 10
