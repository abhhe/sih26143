import pytest
from pathlib import Path
from backend.app.adapters.sar.csiro_adapter import OilSpillDatasetAdapter

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


def test_csiro_load_patch_metadata():
    adapter = OilSpillDatasetAdapter(dataset_dir=FIXTURE_DIR)
    fixture_file = FIXTURE_DIR / "csiro_spill_fixture.json"
    assert fixture_file.exists()

    detection = adapter.load_patch_metadata(fixture_file)
    assert detection.detected is True
    assert detection.confidence == 0.95
    assert detection.area == 4.82
    assert detection.perimeter == 11.4
    assert detection.orientation == 248.5
    assert detection.centroid.latitude == 56.4520
    assert detection.centroid.longitude == 3.2040
    assert detection.spill_mask.type == "Polygon"
    assert len(detection.spill_mask.coordinates[0]) >= 4


def test_csiro_get_patch_by_id():
    adapter = OilSpillDatasetAdapter(dataset_dir=FIXTURE_DIR)
    detection = adapter.get_patch_by_id("CSIRO_S1_OIL_0042_VV")
    assert detection.detected is True
    assert detection.area > 0
    assert detection.look_alike_risk == "low"
