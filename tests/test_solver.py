from datetime import datetime

from astropy.time import Time

from tarapath_core.types import StarObservation
from tarapath_core.solver import estimate_location, _compute_alt_az


def test_solver_recovers_known_location():
    true_lat, true_lon = 37.7749, -122.4194
    ts = Time(datetime(2024, 3, 15, 10, 0, 0))

    stars = [
        ("Sirius", 101.287, -16.716),
        ("Canopus", 95.987, -52.696),
        ("Arcturus", 213.915, 19.182),
    ]

    obs = []
    for i, (name, ra, dec) in enumerate(stars, start=1):
        alt, az = _compute_alt_az(ra, dec, true_lat, true_lon, ts)
        obs.append(
            StarObservation(
                hip=i,
                name=name,
                ra_deg=ra,
                dec_deg=dec,
                observed_alt_deg=alt,
                observed_az_deg=az,
            )
        )

    result = estimate_location(
        obs,
        ts,
        lat_bounds=(true_lat - 5, true_lat + 5),
        lon_bounds=(true_lon - 5, true_lon + 5),
        coarse_step_deg=2.0,
        fine_step_deg=0.5,
    )

    assert abs(result.latitude - true_lat) < 2.0
    assert abs(result.longitude - true_lon) < 2.0

