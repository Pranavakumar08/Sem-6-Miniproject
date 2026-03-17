from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class StarObservation:
    """Observation of a bright star used in the position fix."""

    hip: int
    name: str
    ra_deg: float
    dec_deg: float
    observed_alt_deg: float
    observed_az_deg: float
    weight: float = 1.0


@dataclass
class EstimationResult:
    """Result of a Tarapath position estimate."""

    latitude: float
    longitude: float
    confidence: float
    error_radius_km: float
    used_stars: List[StarObservation] = field(default_factory=list)
    diagnostics: Dict[str, object] = field(default_factory=dict)
    error_message: Optional[str] = None

