import pytest
from datetime import datetime, timezone
from pathlib import Path
from backend.app.adapters.sar.sentinel1_adapter import Sentinel1Adapter
from backend.app.domain.models import BoundingBox

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.mark.asyncio
async def test_sentinel1_load_fixture():
    adapter = Sentinel1Adapter(sar_dir=FIXTURE_DIR, app_mode="DEMO")
    fixture_file = FIXTURE_DIR / "sar_granule_fixture.json"
    assert fixture_file.exists()

    obs = adapter.load_from_fixture_file(fixture_file)
    assert obs.image_id == "S1A_IW_GRDH_1SDV_20260814T061522_054321_066F12_B1A4"
    assert obs.sensor == "Sentinel-1A C-SAR"
    assert obs.resolution == 10.0
    assert obs.latitude == 56.45
    assert obs.longitude == 3.20
    assert "VV" in obs.polarization
    assert obs.orbit_direction == "DESCENDING"
    assert obs.bounding_box is not None
    assert obs.bounding_box.min_latitude == 56.35


@pytest.mark.asyncio
async def test_sentinel1_get_by_id_demo_mode():
    adapter = Sentinel1Adapter(sar_dir=FIXTURE_DIR, app_mode="DEMO")
    obs = await adapter.get_observation_by_id("S1A_IW_GRDH_1SDV_20260814T061522_054321_066F12_B1A4")
    assert obs.image_id == "S1A_IW_GRDH_1SDV_20260814T061522_054321_066F12_B1A4"
    assert obs.latitude == 56.45


@pytest.mark.asyncio
async def test_sentinel1_search_scenes_filter():
    adapter = Sentinel1Adapter(sar_dir=FIXTURE_DIR, app_mode="DEMO")
    bbox = BoundingBox(
        min_latitude=56.0,
        min_longitude=3.0,
        max_latitude=57.0,
        max_longitude=4.0,
    )
    t0 = datetime(2026, 8, 14, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 8, 15, 0, 0, tzinfo=timezone.utc)

    scenes = await adapter.search_scenes(bbox, t0, t1)
    assert len(scenes) >= 1
    assert scenes[0].latitude == 56.45
