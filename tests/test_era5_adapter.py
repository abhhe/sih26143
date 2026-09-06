import pytest
from datetime import datetime, timezone
from pathlib import Path
from backend.app.adapters.metocean.era5_adapter import ERA5Adapter

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.mark.asyncio
async def test_era5_load_fixture():
    adapter = ERA5Adapter(data_dir=FIXTURE_DIR, app_mode="DEMO")
    fixture_file = FIXTURE_DIR / "era5_wind_fixture.json"
    assert fixture_file.exists()

    u10, v10, snapshot = adapter.load_from_fixture_file(fixture_file)
    assert u10 == 6.20
    assert v10 == 4.80
    assert len(snapshot.lats) == 3
    assert len(snapshot.lons) == 3


@pytest.mark.asyncio
async def test_era5_point_sampling_and_interpolation():
    adapter = ERA5Adapter(data_dir=FIXTURE_DIR, app_mode="DEMO")
    t0 = datetime(2026, 8, 14, 6, 0, tzinfo=timezone.utc)

    # Sample right at grid center (56.50, 3.25)
    u, v = await adapter.get_wind_at_point(56.50, 3.25, t0)
    assert isinstance(u, float)
    assert isinstance(v, float)
    assert 5.0 <= u <= 7.0
    assert 4.0 <= v <= 6.0

    # Calculate derived wind speed
    speed = (u**2 + v**2)**0.5
    assert speed > 5.0
