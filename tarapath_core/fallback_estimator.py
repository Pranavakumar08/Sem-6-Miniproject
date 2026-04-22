from datetime import datetime
from pathlib import Path

from .types import EstimationResult
from .solver import load_last_fix


def estimate_from_timezone(
    tz_offset_hours: float,
    timestamp: datetime,
    last_fix_path: Path = Path("data/last_fix.json"),
) -> EstimationResult:
    """
    Derive a rough position from timezone offset and timestamp alone.
    Longitude = tz_offset_hours * 15.0
    Latitude = from last_fix.json if available, else 0.0
    Error radius = 5000 km
    Confidence = 0.1
    """
    longitude = tz_offset_hours * 15.0

    # Fallback to equator if no prior fix is available
    latitude = 0.0

    # Try to load previous GPS fix if it exists
    # load_last_fix internally relies on its own path resolution to data/last_fix.json,
    # but that aligns with the requirement
    prior = load_last_fix()
    if prior is not None:
        latitude, _ = prior

    return EstimationResult(
        latitude=latitude,
        longitude=longitude,
        confidence=0.1,
        error_radius_km=5000.0,
        used_stars=[],
        diagnostics={"fallback": True, "tz_offset_hours": tz_offset_hours},
        error_message=None,
    )
