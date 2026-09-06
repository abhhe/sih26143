import pytest
from datetime import datetime, timezone
from backend.app.core.config import Settings
from backend.app.adapters.sar.sentinel1_adapter import Sentinel1Adapter
from backend.app.adapters.metocean.era5_adapter import ERA5Adapter
from backend.app.adapters.metocean.copernicus_marine_adapter import CopernicusMarineAdapter
from backend.app.adapters.ais.ais_adapter import AISAdapter


def test_settings_demo_mode():
    s = Settings(app_mode="DEMO")
    assert s.is_demo_mode() is True
    assert s.app_mode == "DEMO"


def test_settings_real_mode():
    s = Settings(app_mode="REAL")
    assert s.is_demo_mode() is False
    assert s.app_mode == "REAL"


@pytest.mark.asyncio
async def test_real_mode_missing_credentials_fails_gracefully():
    # In REAL mode without credentials, adapters must raise clear ValueError
    s1_adapter = Sentinel1Adapter(app_mode="REAL")
    with pytest.raises(ValueError, match="REAL mode requires CDSE"):
        await s1_adapter.get_observation_by_id("NON_EXISTENT_ID")

    era5_adapter = ERA5Adapter(app_mode="REAL")
    t0 = datetime(2026, 8, 14, 6, 0, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="REAL mode requires CDS_API_KEY"):
        await era5_adapter.get_wind_at_point(56.45, 3.20, t0)

    cmems_adapter = CopernicusMarineAdapter(app_mode="REAL")
    with pytest.raises(ValueError, match="REAL mode requires COPERNICUS_MARINE_USERNAME"):
        await cmems_adapter.get_current_at_point(56.45, 3.20, t0)

    ais_adapter = AISAdapter(app_mode="REAL")
    with pytest.raises(ValueError, match="REAL mode requires GFW_API_TOKEN"):
        await ais_adapter.query_trajectories(
            bounding_box=None, start_time=t0, end_time=t0  # type: ignore
        )
