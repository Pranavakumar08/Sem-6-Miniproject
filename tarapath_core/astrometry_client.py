from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from pathlib import Path
from PIL import Image

import tetra3


@dataclass
class AstrometrySource:
    ra_deg: float
    dec_deg: float
    name: Optional[str] = None
    hip: Optional[int] = None
    x: Optional[float] = None
    y: Optional[float] = None


@dataclass
class AstrometrySolution:
    success: bool
    ra_center_deg: Optional[float] = None
    dec_center_deg: Optional[float] = None
    scale_arcsec_per_pix: Optional[float] = None
    orientation_deg: Optional[float] = None
    sources: List[AstrometrySource] = None
    error_message: Optional[str] = None
    raw_result: Optional[Dict[str, Any]] = None


class AstrometryClient:
    """Offline plate solver client using tetra3.

    Replaces the HTTP-based Astrometry.net client to provide fast, local plate
    solving while maintaining the same interface for the Tarapath pipeline.
    """

    def __init__(self, api_url: str = "", api_key: Optional[str] = None, timeout_sec: int = 600):
        # We ignore api_url and api_key since we are running offline with tetra3.
        # Retaining the signature for backward compatibility with pipeline.py.
        self.api_url = api_url
        self.api_key = api_key
        self.timeout_sec = timeout_sec
        self.t3 = tetra3.Tetra3()

    def solve_image(self, image_path: str) -> AstrometrySolution:
        """Extract centroids and plate solve using tetra3."""
        try:
            with Image.open(image_path) as img:
                # Ensure image is RGB or L to prevent issues with RGBA
                if img.mode not in ("RGB", "L"):
                    img = img.convert("RGB")
                width, height = img.size

                # Extract star centroids
                centroids = tetra3.get_centroids_from_image(img)

            if len(centroids) < 3:
                return AstrometrySolution(success=False, error_message="Not enough stars detected by tetra3.")

            # Solve from centroids
            res = self.t3.solve_from_centroids(
                centroids,
                size=(height, width),
                return_matches=True
            )

            if res.get("RA") is None:
                return AstrometrySolution(success=False, error_message="tetra3 failed to solve the star field.")

            # Calculate an approximate pixel scale (arcsec per pixel)
            # FOV is the horizontal field of view in degrees.
            fov_deg = res.get("FOV", 0.0)
            scale = (fov_deg * 3600.0) / float(width) if fov_deg and width else 0.0

            sources = []
            matched_stars = res.get("matched_stars", [])
            matched_centroids = res.get("matched_centroids", [])

            for i, star_data in enumerate(matched_stars):
                # matched_stars format: [ra (deg), dec (deg), magnitude]
                ra = float(star_data[0])
                dec = float(star_data[1])
                
                # matched_centroids format: (y, x)
                x, y = None, None
                if i < len(matched_centroids):
                    y, x = matched_centroids[i]
                
                sources.append(
                    AstrometrySource(
                        ra_deg=ra,
                        dec_deg=dec,
                        x=float(x) if x is not None else None,
                        y=float(y) if y is not None else None,
                    )
                )

            return AstrometrySolution(
                success=True,
                ra_center_deg=float(res.get("RA")),
                dec_center_deg=float(res.get("Dec")),
                scale_arcsec_per_pix=scale,
                orientation_deg=float(res.get("Roll")),
                sources=sources,
                raw_result=res,
            )

        except Exception as exc:
            return AstrometrySolution(success=False, error_message=f"tetra3 error: {str(exc)}")
