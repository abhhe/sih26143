import pytest
from datetime import datetime, timezone
from pathlib import Path
from backend.app.adapters.metocean.copernicus_marine_adapter import CopernicusMarineAdapter

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.mark.asyncio
async def test_cmems_currents_load_fixture():
    adapter = CopernicusMarineAdapter(data_dir=FIXTURE_DIR, app_mode="DEMO")
    fixture_file = FIXTURE_DIR / "cmems_current_fixture.json"
    assert fixture_file.exists()

    uo, vo, snapshot = adapter.load_from_fixture_file(fixture_file)
    assert uo == 0.32
    assert vo == 0.14
    assert len(snapshot.lats) == 3


@pytest.mark.asyncio
async def test_cmems_get_current_at_point():
    adapter = CopernicusMarineAdapter(data_dir=FIXTURE_DIR, app_mode="DEMO")
    t0 = datetime(2026, 8, 14, 6, 0, tzinfo=timezone.utc)

    uo, vo = await adapter.get_current_at_point(56.50, 3.25, t0)
    assert isinstance(uo, float)
    assert isinstance(vo, float)
    assert 0.20 <= uo <= 0.40
    assert 0.05 <= vo <= 0.25


@pytest.mark.asyncio
async def test_cmems_combined_environmental_state():
    adapter = CopernicusMarineAdapter(data_dir=FIXTURE_DIR, app_mode="DEMO")
    t0 = datetime(2026, 8, 14, 6, 0, tzinfo=timezone.utc)

    env_state = await adapter.get_environmental_state(56.45, 3.20, t0)
    assert env_state.latitude == 56.45
    assert env_state.longitude == 3.20
    assert env_state.wind_u != 0.0
    assert env_state.wind_v != 0.0
    assert env_state.current_u != 0.0
    assert env_state.current_v != 0.0
    assert env_state.wind_speed_ms > 0.0
    assert env_state.current_speed_ms > 0.0
