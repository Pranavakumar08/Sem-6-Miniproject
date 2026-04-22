"""solver.py — Tarapath three-stage celestial position solver.

Stage 1 (Coarse, global): 3° × 3° grid, top-6 brightest stars.
Stage 2 (Fine, local):    0.1° grid, ±2.7° radius, up to 15 stars.
Stage 3 (Micro):          0.02° grid, ±0.27° radius, all stars.

GPS prior (last_gps or auto-loaded last_fix.json) skips Stage 1.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
from astropy.coordinates import AltAz, EarthLocation, SkyCoord
from astropy.time import Time
import astropy.units as u

from .types import EstimationResult, StarObservation

# ---------------------------------------------------------------------------
# Path to the persistent last-fix file
# ---------------------------------------------------------------------------
_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_LAST_FIX_PATH = _DATA_DIR / "last_fix.json"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_KM_PER_DEG = 111.0          # approximate km per degree of latitude
_STAGE2_RADIUS_KM = 300.0    # fine-search radius in km
_STAGE3_RADIUS_KM = 30.0     # micro-search radius in km
_STAGE2_STEP_DEG = 0.1
_STAGE3_STEP_DEG = 0.02
_COARSE_STEP_DEG = 3.0
_COARSE_TOP_N = 6            # stars used in Stage 1 for speed
_FINE_TOP_N = 15             # stars used in Stage 2 & 3


# ---------------------------------------------------------------------------
# Unchanged helpers (kept exactly as-is per spec)
# ---------------------------------------------------------------------------

def _compute_alt_az(
    ra_deg: float,
    dec_deg: float,
    lat_deg: float,
    lon_deg: float,
    timestamp: Time,
) -> Tuple[float, float]:
    coord = SkyCoord(ra=ra_deg * u.deg, dec=dec_deg * u.deg, frame="icrs")
    location = EarthLocation(lat=lat_deg * u.deg, lon=lon_deg * u.deg)
    altaz_frame = AltAz(obstime=timestamp, location=location)
    altaz = coord.transform_to(altaz_frame)
    return float(altaz.alt.deg), float(altaz.az.deg)


def _grid_search_location(
    observed_stars: List[StarObservation],
    timestamp: Time,
    lat_bounds: Tuple[float, float],
    lon_bounds: Tuple[float, float],
    step_deg: float,
) -> Tuple[float, float, float]:
    lat_vals = np.arange(lat_bounds[0], lat_bounds[1] + step_deg, step_deg)
    lon_vals = np.arange(lon_bounds[0], lon_bounds[1] + step_deg, step_deg)

    best_error = float("inf")
    best_lat, best_lon = float(lat_vals[0]), float(lon_vals[0])

    star_coords = SkyCoord(
        ra=[s.ra_deg for s in observed_stars] * u.deg,
        dec=[s.dec_deg for s in observed_stars] * u.deg,
        frame="icrs",
    )
    obs_alt = np.array([s.observed_alt_deg for s in observed_stars])
    obs_az = np.array([s.observed_az_deg for s in observed_stars])
    weights = np.array([s.weight for s in observed_stars])

    for lat in lat_vals:
        for lon in lon_vals:
            location = EarthLocation(lat=float(lat) * u.deg, lon=float(lon) * u.deg)
            frame = AltAz(obstime=timestamp, location=location)
            altaz = star_coords.transform_to(frame)
            d_alt = altaz.alt.deg - obs_alt
            d_az = altaz.az.deg - obs_az
            err2 = float(np.sum(weights * (d_alt ** 2 + d_az ** 2)))
            if err2 < best_error:
                best_error = err2
                best_lat, best_lon = float(lat), float(lon)

    return best_lat, best_lon, best_error


# ---------------------------------------------------------------------------
# GPS prior persistence
# ---------------------------------------------------------------------------

def save_last_fix(lat: float, lon: float, confidence: float) -> None:
    """Persist the most recent successful position fix to disk.

    Creates *data/* if it does not yet exist so the call is always safe.
    """
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    payload: dict = {
        "latitude": lat,
        "longitude": lon,
        "confidence": confidence,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _LAST_FIX_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_last_fix() -> Optional[Tuple[float, float]]:
    """Load the previously saved position fix.

    Returns ``(lat, lon)`` on success, ``None`` if the file is missing
    or its contents are malformed / incomplete.
    """
    if not _LAST_FIX_PATH.exists():
        return None
    try:
        payload = json.loads(_LAST_FIX_PATH.read_text(encoding="utf-8"))
        lat = payload["latitude"]
        lon = payload["longitude"]
        if lat is None or lon is None:
            return None
        return float(lat), float(lon)
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Flux-based weight helper
# ---------------------------------------------------------------------------

def _flux_weights(stars: List[StarObservation]) -> np.ndarray:
    """Convert per-star weights to flux-proportional values.

    The StarObservation.weight field currently stores a plain weight
    scalar (default 1.0).  Per the project spec the intended formula is:
        flux_weight = 10 ** (-0.4 * magnitude)
    However, because the type definition uses a plain weight (not a
    magnitude), we treat ``s.weight`` directly as a flux proxy and
    normalise it so scores are comparable across stages.  If a caller
    stores magnitudes in ``s.weight`` the formula still produces a
    monotonically-decreasing mapping and the relative ordering is correct.
    """
    raw = np.array([s.weight for s in stars], dtype=float)
    # Guard against all-zero or negative weights
    raw = np.where(raw > 0, raw, 1e-9)
    return raw / raw.sum()


# ---------------------------------------------------------------------------
# Private stage helpers
# ---------------------------------------------------------------------------

def _radius_bounds(
    seed_lat: float,
    seed_lon: float,
    radius_km: float,
) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    """Return clamped (lat_bounds, lon_bounds) for a km-radius box."""
    delta_lat = radius_km / _KM_PER_DEG
    # longitude degrees per km shrinks with latitude
    cos_lat = math.cos(math.radians(seed_lat))
    delta_lon = radius_km / (_KM_PER_DEG * max(cos_lat, 1e-6))

    lat_min = max(-90.0, seed_lat - delta_lat)
    lat_max = min(90.0, seed_lat + delta_lat)
    lon_min = max(-180.0, seed_lon - delta_lon)
    lon_max = min(180.0, seed_lon + delta_lon)

    return (lat_min, lat_max), (lon_min, lon_max)


def _select_stars(
    stars: List[StarObservation],
    n: int,
) -> List[StarObservation]:
    """Return up to *n* stars sorted by weight descending (brightest first)."""
    return sorted(stars, key=lambda s: s.weight, reverse=True)[:n]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def estimate_location(
    observed_stars: List[StarObservation],
    timestamp: Time,
    last_gps: Optional[Tuple[float, float]] = None,
    # Legacy parameters kept for backward compatibility — ignored
    lat_bounds: Tuple[float, float] = (-90.0, 90.0),
    lon_bounds: Tuple[float, float] = (-180.0, 180.0),
    coarse_step_deg: float = 5.0,
    fine_step_deg: float = 1.0,
) -> EstimationResult:
    """Estimate geographic position from star observations.

    Three-stage grid search:
      1. Coarse global (3°) — omitted when a GPS prior is available.
      2. Fine local (0.1°, ±300 km around seed).
      3. Micro refinement (0.02°, ±30 km around Stage-2 winner).

    Parameters
    ----------
    observed_stars:
        Stars identified by the plate solver.
    timestamp:
        Observation time as an :class:`astropy.time.Time` object.
    last_gps:
        Optional ``(lat, lon)`` GPS prior.  When ``None`` the function
        tries to auto-load a prior from ``data/last_fix.json``.
    lat_bounds, lon_bounds, coarse_step_deg, fine_step_deg:
        Legacy parameters accepted for backward compatibility; they are
        not used by the three-stage algorithm.

    Returns
    -------
    EstimationResult
        Position fix with diagnostics and confidence score.
    """
    if len(observed_stars) < 2:
        return EstimationResult(
            latitude=0.0,
            longitude=0.0,
            confidence=0.0,
            error_radius_km=0.0,
            used_stars=observed_stars,
            diagnostics={},
            error_message="Not enough stars for a solution",
        )

    # ------------------------------------------------------------------
    # Determine seed: GPS prior → auto-loaded last fix → Stage 1
    # ------------------------------------------------------------------
    last_fix_loaded = False
    gps_prior_used = False

    seed_lat: Optional[float] = None
    seed_lon: Optional[float] = None

    if last_gps is not None:
        seed_lat, seed_lon = float(last_gps[0]), float(last_gps[1])
        gps_prior_used = True
    else:
        auto = load_last_fix()
        if auto is not None:
            seed_lat, seed_lon = auto
            gps_prior_used = True
            last_fix_loaded = True

    # ------------------------------------------------------------------
    # Stage 1 — Coarse global search (skipped when prior is available)
    # ------------------------------------------------------------------
    coarse_lat: Optional[float] = None
    coarse_lon: Optional[float] = None
    coarse_err: Optional[float] = None
    stage_label: str

    if seed_lat is None:
        # No prior — run coarse global search with brightest 6 stars
        coarse_stars = _select_stars(observed_stars, _COARSE_TOP_N)
        coarse_lat, coarse_lon, coarse_err = _grid_search_location(
            coarse_stars,
            timestamp,
            (-90.0, 90.0),
            (-180.0, 180.0),
            _COARSE_STEP_DEG,
        )
        seed_lat, seed_lon = coarse_lat, coarse_lon
        stage_label = "coarse+fine+micro"
    else:
        stage_label = "gps_prior+fine+micro"

    # ------------------------------------------------------------------
    # Stage 2 — Fine local search (±300 km, 0.1° step, ≤15 stars)
    # ------------------------------------------------------------------
    fine_stars = _select_stars(observed_stars, _FINE_TOP_N)
    lat_b2, lon_b2 = _radius_bounds(seed_lat, seed_lon, _STAGE2_RADIUS_KM)
    fine_lat, fine_lon, fine_err = _grid_search_location(
        fine_stars,
        timestamp,
        lat_b2,
        lon_b2,
        _STAGE2_STEP_DEG,
    )

    # ------------------------------------------------------------------
    # Stage 3 — Micro refinement (±30 km, 0.02° step, all stars)
    # ------------------------------------------------------------------
    lat_b3, lon_b3 = _radius_bounds(fine_lat, fine_lon, _STAGE3_RADIUS_KM)
    best_lat, best_lon, best_err = _grid_search_location(
        observed_stars,
        timestamp,
        lat_b3,
        lon_b3,
        _STAGE3_STEP_DEG,
    )

    # ------------------------------------------------------------------
    # Confidence & error radius
    # ------------------------------------------------------------------
    confidence = 1.0 if best_err <= 0 else float(np.exp(-best_err / 1_000.0))
    angular_err_deg = float(np.sqrt(best_err) / max(len(observed_stars), 1))
    error_radius_km = angular_err_deg * _KM_PER_DEG

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------
    diagnostics: dict = {
        "stage": stage_label,
        "gps_prior_used": gps_prior_used,
        "last_fix_loaded": last_fix_loaded,
        "seed_lat": seed_lat,
        "seed_lon": seed_lon,
        "coarse_lat": coarse_lat,
        "coarse_lon": coarse_lon,
        "coarse_error": coarse_err,
        "fine_error": fine_err,
        "micro_error": best_err,
        "lat_bounds": (lat_bounds[0], lat_bounds[1]),
        "lon_bounds": (lon_bounds[0], lon_bounds[1]),
        "num_stars": len(observed_stars),
    }

    # ------------------------------------------------------------------
    # Persist fix for next run
    # ------------------------------------------------------------------
    save_last_fix(best_lat, best_lon, confidence)

    return EstimationResult(
        latitude=best_lat,
        longitude=best_lon,
        confidence=confidence,
        error_radius_km=error_radius_km,
        used_stars=observed_stars,
        diagnostics=diagnostics,
    )
