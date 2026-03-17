from datetime import datetime
from pathlib import Path
from typing import Optional

from astropy.time import Time

from .catalog import StarCatalog
from .catalog_match import cross_match_sources
from .astrometry_client import AstrometryClient
from .exif_utils import read_exif_datetime
from .solver import estimate_location, _compute_alt_az
from .types import EstimationResult


class TarapathConfig:
    """Lightweight configuration for the Tarapath pipeline."""

    def __init__(
        self,
        catalog_path: str | Path = "data/star_catalog/hyg_stars.csv",
        astrometry_url: str = "https://nova.astrometry.net",
        astrometry_api_key: Optional[str] = None,
        match_tolerance_deg: float = 1.0,
        lat_bounds: tuple[float, float] = (-90.0, 90.0),
        lon_bounds: tuple[float, float] = (-180.0, 180.0),
    ):
        self.catalog_path = str(catalog_path)
        self.astrometry_url = astrometry_url
        self.astrometry_api_key = astrometry_api_key
        self.match_tolerance_deg = match_tolerance_deg
        self.lat_bounds = lat_bounds
        self.lon_bounds = lon_bounds


def run_tarapath(
    image_path: str,
    timestamp_override: Optional[datetime] = None,
    config: Optional[TarapathConfig] = None,
) -> EstimationResult:
    """High-level entrypoint: image -> estimated position."""
    cfg = config or TarapathConfig()

    # 1. Determine timestamp
    ts = timestamp_override or read_exif_datetime(image_path)
    if ts is None:
        return EstimationResult(
            latitude=0.0,
            longitude=0.0,
            confidence=0.0,
            error_radius_km=0.0,
            used_stars=[],
            diagnostics={},
            error_message="Unable to determine timestamp (no EXIF and no override)",
        )

    astro_time = Time(ts)

    # 2. Plate solve via Astrometry.net
    client = AstrometryClient(api_url=cfg.astrometry_url, api_key=cfg.astrometry_api_key)
    solution = client.solve_image(image_path)
    if not solution.success or solution.sources is None:
        return EstimationResult(
            latitude=0.0,
            longitude=0.0,
            confidence=0.0,
            error_radius_km=0.0,
            used_stars=[],
            diagnostics={"astrometry_error": solution.error_message},
            error_message=solution.error_message or "Astrometry.net solve failed",
        )

    # 3. Load catalog and cross-match
    catalog = StarCatalog(Path(cfg.catalog_path))
    matched = cross_match_sources(catalog, solution.sources, tolerance_deg=cfg.match_tolerance_deg)
    if len(matched) < 2:
        return EstimationResult(
            latitude=0.0,
            longitude=0.0,
            confidence=0.0,
            error_radius_km=0.0,
            used_stars=matched,
            diagnostics={"astrometry_sources": len(solution.sources)},
            error_message="Not enough matched bright stars for a solution",
        )

    # 4. Derive apparent Alt/Az at nominal location (0, 0) for each star.
    #    The solver will still vary the location; these serve as synthetic observations.
    obs_with_altaz = []
    for star in matched:
        alt, az = _compute_alt_az(star.ra_deg, star.dec_deg, 0.0, 0.0, astro_time)
        star.observed_alt_deg = alt
        star.observed_az_deg = az
        obs_with_altaz.append(star)

    # 5. Run the location solver
    result = estimate_location(
        obs_with_altaz,
        astro_time,
        lat_bounds=cfg.lat_bounds,
        lon_bounds=cfg.lon_bounds,
    )
    return result

