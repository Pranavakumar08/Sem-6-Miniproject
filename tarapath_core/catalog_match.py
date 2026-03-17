from typing import List
import math

from .catalog import StarCatalog, StarRecord
from .astrometry_client import AstrometrySource
from .types import StarObservation


def _angular_sep_deg(ra1_deg: float, dec1_deg: float, ra2_deg: float, dec2_deg: float) -> float:
    """Great-circle angular separation in degrees."""
    ra1 = math.radians(ra1_deg)
    ra2 = math.radians(ra2_deg)
    dec1 = math.radians(dec1_deg)
    dec2 = math.radians(dec2_deg)
    cos_d = (
        math.sin(dec1) * math.sin(dec2)
        + math.cos(dec1) * math.cos(dec2) * math.cos(ra1 - ra2)
    )
    cos_d = max(-1.0, min(1.0, cos_d))
    return math.degrees(math.acos(cos_d))


def cross_match_sources(
    catalog: StarCatalog,
    sources: List[AstrometrySource],
    tolerance_deg: float = 1.0,
) -> List[StarObservation]:
    """Match Astrometry.net sources to local bright-star catalog."""
    df = catalog.dataframe
    obs: List[StarObservation] = []

    for src in sources:
        best_row: StarRecord | None = None
        best_sep = float("inf")
        for _, row in df.iterrows():
            sep = _angular_sep_deg(src.ra_deg, src.dec_deg, float(row["ra"]), float(row["dec"]))
            if sep < best_sep:
                best_sep = sep
                best_row = row
        if best_row is None or best_sep > tolerance_deg:
            continue

        rec = StarRecord(
            hip=int(best_row["hip"]),
            ra_deg=float(best_row["ra"]),
            dec_deg=float(best_row["dec"]),
            mag=float(best_row["mag"]),
            name=str(best_row["name"]),
        )

        obs.append(
            StarObservation(
                hip=rec.hip,
                name=rec.name,
                ra_deg=rec.ra_deg,
                dec_deg=rec.dec_deg,
                # observed Alt/Az will be filled by the solver pipeline
                observed_alt_deg=0.0,
                observed_az_deg=0.0,
                weight=1.0,
            )
        )

    return obs

