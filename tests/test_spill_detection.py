import pytest
import numpy as np
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from backend.app.adapters.detection.sar_preprocessor import SARPreprocessor
from backend.app.adapters.detection.spill_detector import SARSpillDetector
from backend.app.domain.models import SatelliteObservation, SpillDetection
from backend.app.main import app


def test_preprocessor_to_decibels():
    intensity = np.array([1.0, 10.0, 100.0], dtype=np.float32)
    db = SARPreprocessor.to_decibels(intensity)
    assert np.isclose(db[0], 0.0, atol=1e-4)
    assert np.isclose(db[1], 10.0, atol=1e-4)
    assert np.isclose(db[2], 20.0, atol=1e-4)


def test_preprocessor_percentile_normalize():
    arr = np.linspace(0, 100, 1000).astype(np.float32)
    norm = SARPreprocessor.percentile_normalize(arr, p_low=1.0, p_high=99.0)
    assert norm.min() >= 0.0
    assert norm.max() <= 1.0
    assert np.isclose(norm.mean(), 0.5, atol=0.05)


def test_preprocessor_lee_filter():
    # Synthetic image with random gamma speckle noise
    np.random.seed(42)
    clean_signal = np.full((64, 64), 0.5, dtype=np.float32)
    clean_signal[20:44, 20:44] = 0.2  # Dark patch
    noise = np.random.gamma(4.0, 0.25, (64, 64)).astype(np.float32)
    noisy_img = clean_signal * noise

    filtered = SARPreprocessor.lee_filter(noisy_img, window_size=5, enl=4.0)
    # Variance in uniform background should be significantly reduced
    var_noisy = np.var(noisy_img[:20, :20])
    var_filtered = np.var(filtered[:20, :20])
    assert var_filtered < var_noisy


@pytest.mark.asyncio
async def test_spill_detector_synthetic_scene():
    detector = SARSpillDetector(pixel_spacing_m=10.0, min_spill_pixels=20)
    obs = SatelliteObservation(
        image_id="TEST_SYNTHETIC_SAR_01",
        timestamp=datetime(2026, 8, 14, 6, 15, tzinfo=timezone.utc),
        latitude=56.45,
        longitude=3.20,
        image_path="synthetic_memory_patch.tiff",
        sensor="Sentinel-1A C-SAR",
        resolution=10.0,
    )

    result = await detector.detect_spill(obs, confidence_threshold=0.50)
    assert isinstance(result, SpillDetection)
    assert result.detected is True
    assert result.confidence >= 0.70
    assert result.area > 0.1  # Area in km²
    assert result.perimeter > 0.5  # Perimeter in km
    assert 0.0 <= result.orientation <= 360.0
    assert result.spill_mask.type == "Polygon"
    assert len(result.spill_mask.coordinates[0]) >= 4
    assert 56.40 <= result.centroid.latitude <= 56.50
    assert 3.10 <= result.centroid.longitude <= 3.30
    assert result.look_alike_risk in ("low", "medium")


def test_look_alike_discrimination_rules():
    detector = SARSpillDetector()

    # Case 1: Ship wake (high elongation > 14.0)
    risk, conf, cat = detector._classify_look_alike(
        area_km2=0.5, elongation=18.5, complexity=2.1, perimeter_km=15.0
    )
    assert risk == "high"
    assert cat == "ship_wake"

    # Case 2: Low-wind sea area (massive area > 40 km² and low boundary complexity)
    risk, conf, cat = detector._classify_look_alike(
        area_km2=65.0, elongation=2.2, complexity=1.1, perimeter_km=30.0
    )
    assert risk == "high"
    assert cat == "low_wind_area"

    # Case 3: Natural biogenic film (high fractal complexity > 5.5)
    risk, conf, cat = detector._classify_look_alike(
        area_km2=2.4, elongation=3.0, complexity=6.2, perimeter_km=14.0
    )
    assert risk == "medium"
    assert cat == "natural_film"

    # Case 4: Mineral oil slick
    risk, conf, cat = detector._classify_look_alike(
        area_km2=4.8, elongation=4.5, complexity=2.4, perimeter_km=11.2
    )
    assert risk == "low"
    assert cat == "likely_oil_spill"
    assert conf >= 0.90


def test_api_satellite_analyze_endpoint():
    client = TestClient(app)

    # 1. Health check
    res_health = client.get("/api/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "online"

    # 2. Analyze route with form data
    res = client.post(
        "/api/satellite/analyze",
        data={
            "image_id": "S1A_IW_GRDH_1SDV_20260814T061522_054321_066F12_B1A4",
            "latitude": "56.45",
            "longitude": "3.20",
            "resolution": "10.0",
            "confidence_threshold": "0.50",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert "detected" in data
    assert "confidence" in data
    assert "centroid" in data
    assert "bounding_box" in data
    assert "spill_mask" in data
    assert "look_alike_risk" in data
    assert data["detected"] is True
    assert data["area"] > 0
