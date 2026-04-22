from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
from astropy.time import Time

from .catalog import StarCatalog
from .catalog_match import cross_match_sources
from .astrometry_client import AstrometryClient, AstrometrySolution
from .exif_utils import read_exif_datetime
from .types import EstimationResult, StarObservation


class TarapathConfig:
    """Lightweight configuration for the Tarapath pipeline."""

    def __init__(
        self,
        catalog_path: str | Path = "data/star_catalog/hyg_stars.csv",
        astrometry_url: str = "https://nova.astrometry.net",
        astrometry_api_key: Optional[str] = None,
        match_tolerance_deg: float = 1.0,
        assumed_camera_tilt_deg: float = 0.0,
    ):
        self.catalog_path = str(catalog_path)
        self.astrometry_url = astrometry_url
        self.astrometry_api_key = astrometry_api_key
        self.match_tolerance_deg = match_tolerance_deg
        self.assumed_camera_tilt_deg = assumed_camera_tilt_deg


def _zenith_estimate(solution: AstrometrySolution, astro_time: Time) -> tuple[float, float]:
    """
    Derive observer lat/lon directly from the plate solution's field center.

    Astronomical basis (zenith method):
      - The declination of the zenith equals the observer's latitude.
      - The right ascension of the zenith equals the Local Sidereal Time (LST).
      - LST = GMST + longitude  →  longitude = RA_zenith − GMST

    This is accurate when the camera is pointed roughly toward the zenith.
    """
    gmst_deg = float(astro_time.sidereal_time("mean", "greenwich").deg)
    # Astrometry.net returns coordinates in the J2000 epoch.
    # We must precess them to the current observation date before calculating longitude,
    # otherwise we inherit ~24 years of Earth's axial wobble error (~40 km).
    import astropy.units as u
    from astropy.coordinates import SkyCoord, FK5

    # 1. Start with the J2000 coordinates from the plate solution
    j2000_coord = SkyCoord(ra=solution.ra_center_deg * u.deg, dec=solution.dec_center_deg * u.deg, frame='icrs')
    
    # 2. Transform to the coordinate frame of the observation date
    obs_date_frame = FK5(equinox=astro_time)
    current_coord = j2000_coord.transform_to(obs_date_frame)

    lat = current_coord.dec.deg          # zenith dec = latitude
    lon = current_coord.ra.deg - gmst_deg  # zenith RA = GMST + lon
    # Normalize longitude to [-180, 180]
    lon = ((lon + 180.0) % 360.0) - 180.0
    return lat, lon


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
    if not solution.success:
        return EstimationResult(
            latitude=0.0,
            longitude=0.0,
            confidence=0.0,
            error_radius_km=0.0,
            used_stars=[],
            diagnostics={"astrometry_error": solution.error_message},
            error_message=solution.error_message or "Astrometry.net solve failed",
        )

    # 3. Direct position estimate from field center (zenith method) — fast, algebraic
    direct_lat, direct_lon = _zenith_estimate(solution, astro_time)

    # 4. Load catalog and cross-match to get named bright stars in the image
    catalog = StarCatalog(Path(cfg.catalog_path))
    sources = solution.sources or []
    matched: list[StarObservation] = []

    if sources:
        matched = cross_match_sources(
            catalog, sources, tolerance_deg=cfg.match_tolerance_deg
        )

    # 5. Calculate error and confidence
    # RMSE from tetra3 is in arcseconds — convert to degrees then to km on Earth's surface
    rmse_arcsec = solution.raw_result.get("RMSE", 0.0) if solution.raw_result else 0.0
    scale_deg_per_pix = (solution.scale_arcsec_per_pix or 0.0) / 3600.0
    rmse_deg = (rmse_arcsec / 3600.0)  # tetra3 RMSE is already in arcsec

    # Convert angular pointing error to surface distance (1 deg ~ 111.12 km)
    base_error_km = rmse_deg * 111.12

    # Tilt error: each degree of unknown camera tilt adds ~111 km uncertainty
    tilt_error_km = cfg.assumed_camera_tilt_deg * 111.12

    error_km = base_error_km + tilt_error_km

    # Confidence: scaled by number of matched stars (saturates at 10+) × tilt penalty
    n_matches = solution.raw_result.get("Matches", 0) if solution.raw_result else 0
    confidence = min(1.0, n_matches / 10.0) * (
        1.0 if cfg.assumed_camera_tilt_deg == 0
        else max(0.01, np.exp(-cfg.assumed_camera_tilt_deg / 5.0))
    )

    return EstimationResult(
        latitude=direct_lat,
        longitude=direct_lon,
        confidence=confidence,
        error_radius_km=error_km,
        used_stars=matched,
        diagnostics={
            "method": "zenith_direct",
            "ra_center": solution.ra_center_deg,
            "dec_center": solution.dec_center_deg,
            "gmst_deg": float(astro_time.sidereal_time("mean", "greenwich").deg),
            "astrometry_sources": len(sources),
            "assumed_tilt": cfg.assumed_camera_tilt_deg,
        },
    )
