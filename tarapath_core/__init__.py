"""
Tarapath core package.

Provides the non-UI pipeline for estimating a ship's position from
night-sky photographs using a local star catalog, Astrometry.net,
and Astropy-based celestial navigation.

Public API
----------
>>> from tarapath_core import run_tarapath, TarapathConfig
>>> result = run_tarapath("sky.jpg")
"""

from .pipeline import run_tarapath, TarapathConfig
from .types import EstimationResult, StarObservation

__all__ = [
    "run_tarapath",
    "TarapathConfig",
    "EstimationResult",
    "StarObservation",
]

