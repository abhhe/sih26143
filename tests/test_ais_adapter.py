# pyrefly: ignore [missing-import]
import pytest
from datetime import datetime, timezone
from pathlib import Path
from backend.app.adapters.ais.ais_adapter import AISAdapter
from backend.app.domain.models import BoundingBox

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


def test_ais_load_from_csv():
    adapter = AISAdapter(data_dir=FIXTURE_DIR, app_mode="DEMO")
    fixture_file = FIXTURE_DIR / "marine_cadastre_ais_fixture.csv"
    assert fixture_file.exists()

    trajectories = adapter.load_from_csv(fixture_file)
    assert len(trajectories) == 3

    # Check Tanker (Nordic Titan)
    tanker = next((t for t in trajectories if t.mmsi == "244123456"), None)
    assert tanker is not None
    assert tanker.vessel_name == "MT NORDIC TITAN"
    assert tanker.vessel_type == "Tanker"
    assert len(tanker.points) == 4

    # Verify points are strictly chronological
    for i in range(len(tanker.points) - 1):
        assert tanker.points[i].timestamp <= tanker.points[i + 1].timestamp

    # Verify required fields are populated
    p = tanker.points[2]  # Peak encounter ping
    assert p.mmsi == "244123456"
    assert p.latitude == 56.3260
    assert p.longitude == 3.0210
    assert p.speed == 9.1
    assert p.course == 45.0
    assert p.heading == 45.0


@pytest.mark.asyncio
async def test_ais_corridor_query_filtering():
    adapter = AISAdapter(data_dir=FIXTURE_DIR, app_mode="DEMO")
    
    # Query spatial corridor around the source zone
    bbox = BoundingBox(
        min_latitude=56.25,
        min_longitude=2.90,
        max_latitude=56.40,
        max_longitude=3.10,
    )
    t_start = datetime(2026, 8, 13, 11, 0, tzinfo=timezone.utc)
    t_end = datetime(2026, 8, 13, 16, 0, tzinfo=timezone.utc)

    results = await adapter.query_trajectories(bbox, t_start, t_end)
    assert len(results) >= 1
    # Nordic Titan should be in the corridor
    mmsis = [t.mmsi for t in results]
    assert "244123456" in mmsis
    # Sea Hunter (fishing south) should NOT be in this tight corridor
    assert "219654321" not in mmsis
