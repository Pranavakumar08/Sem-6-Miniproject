from typing import List, Tuple

import numpy as np
from astropy.coordinates import SkyCoord, EarthLocation, AltAz
from astropy.time import Time
import astropy.units as u

from .types import StarObservation, EstimationResult


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
    best_error = float("inf")
    best_lat, best_lon = 0.0, 0.0

    lat_vals = np.arange(lat_bounds[0], lat_bounds[1] + step_deg, step_deg)
    lon_vals = np.arange(lon_bounds[0], lon_bounds[1] + step_deg, step_deg)

    for lat in lat_vals:
        for lon in lon_vals:
            err2_sum = 0.0
            for star in observed_stars:
                pred_alt, pred_az = _compute_alt_az(star.ra_deg, star.dec_deg, lat, lon, timestamp)
                d_alt = pred_alt - star.observed_alt_deg
                d_az = pred_az - star.observed_az_deg
                err2_sum += star.weight * (d_alt ** 2 + d_az ** 2)
            if err2_sum < best_error:
                best_error = err2_sum
                best_lat, best_lon = float(lat), float(lon)

    return best_lat, best_lon, best_error


def estimate_location(
    observed_stars: List[StarObservation],
    timestamp: Time,
    lat_bounds: Tuple[float, float] = (-90.0, 90.0),
    lon_bounds: Tuple[float, float] = (-180.0, 180.0),
    coarse_step_deg: float = 5.0,
    fine_step_deg: float = 1.0,
) -> EstimationResult:
    """Estimate observer location by matching observed stars to predicted Alt/Az."""
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

    # Coarse search
    coarse_lat, coarse_lon, coarse_err = _grid_search_location(
        observed_stars, timestamp, lat_bounds, lon_bounds, coarse_step_deg
    )

    # Fine search around coarse solution
    lat_min = max(-90.0, coarse_lat - coarse_step_deg)
    lat_max = min(90.0, coarse_lat + coarse_step_deg)
    lon_min = max(-180.0, coarse_lon - coarse_step_deg)
    lon_max = min(180.0, coarse_lon + coarse_step_deg)

    best_lat, best_lon, best_err = _grid_search_location(
        observed_stars,
        timestamp,
        (lat_min, lat_max),
        (lon_min, lon_max),
        fine_step_deg,
    )

    # Simple heuristic: map error to confidence [0, 1]
    # These constants are empirical and can be tuned with real data.
    if best_err <= 0:
        confidence = 1.0
    else:
        confidence = float(np.exp(-best_err / 1_000.0))

    # Approximate error radius in km from angular error
    # Treat sqrt(error) in degrees as an angular discrepancy and convert to km.
    angular_err_deg = float(np.sqrt(best_err) / max(len(observed_stars), 1))
    # 1 deg ~ 111 km on Earth's surface
    error_radius_km = angular_err_deg * 111.0

    diagnostics = {
        "coarse_error": coarse_err,
        "fine_error": best_err,
        "coarse_lat": coarse_lat,
        "coarse_lon": coarse_lon,
        "lat_bounds": (lat_bounds[0], lat_bounds[1]),
        "lon_bounds": (lon_bounds[0], lon_bounds[1]),
        "num_stars": len(observed_stars),
    }

    return EstimationResult(
        latitude=best_lat,
        longitude=best_lon,
        confidence=confidence,
        error_radius_km=error_radius_km,
        used_stars=observed_stars,
        diagnostics=diagnostics,
    )

