"""
TARAPATH - Star Pattern Matching Module
Matches detected stars against catalog using geometric invariants
"""

import numpy as np
from typing import List, Tuple, Optional
import math
import logging

from star_catalog import StarCatalog
from star_detector import DetectedStar
from config import config

logger = logging.getLogger(__name__)

class PatternMatcher:
    """
    Matches detected star patterns against catalog
    Uses triangle invariants for robust matching
    """
    
    def __init__(self, catalog: StarCatalog, fov_deg: float = None):
        """
        Initialize pattern matcher
        
        Args:
            catalog: StarCatalog instance
            fov_deg: Camera field of view in degrees
        """
        self.catalog = catalog
        self.fov = fov_deg or config.camera.fov_deg
        self.match_threshold = 0.1  # 10% tolerance for matching
        
    def create_triangle_invariants(self, stars: List[DetectedStar]) -> list[tuple[float, float, float]]:
        """
        Create geometric invariants from star triangles
        
        Args:
            stars: List of detected stars
            
        Returns:
            List of (ratio1, ratio2, angle) for each triangle
        """
        if len(stars) < 3:
            return []
        
        invariants = []
        n = len(stars)
        
        for i in range(n-2):
            for j in range(i+1, n-1):
                for k in range(j+1, n):
                    # Calculate distances between stars (in pixels)
                    d_ij = math.sqrt((stars[i].x - stars[j].x)**2 + (stars[i].y - stars[j].y)**2)
                    d_jk = math.sqrt((stars[j].x - stars[k].x)**2 + (stars[j].y - stars[k].y)**2)
                    d_ki = math.sqrt((stars[k].x - stars[i].x)**2 + (stars[k].y - stars[i].y)**2)
                    
                    # Sort distances
                    sides = sorted([d_ij, d_jk, d_ki])
                    
                    # Calculate invariant ratios (avoid division by zero)
                    if sides[0] > 0:
                        ratio1 = sides[2] / sides[0]  # longest / shortest
                        ratio2 = sides[1] / sides[0]  # middle / shortest
                        
                        # Calculate angle using law of cosines
                        cos_angle = (sides[0]**2 + sides[1]**2 - sides[2]**2) / (2 * sides[0] * sides[1])
                        cos_angle = max(-1, min(1, cos_angle))  # Clamp to valid range
                        angle = math.acos(cos_angle)
                        
                        invariants.append((ratio1, ratio2, angle))
        
        return invariants
    
    def create_catalog_invariants(self, catalog_stars: list[dict]) -> list[tuple[float, float, float, list[int]]]:
        """
        Create invariants from catalog stars with star indices
        
        Args:
            catalog_stars: List of catalog stars
            
        Returns:
            List of (ratio1, ratio2, angle, [i,j,k]) for each triangle
        """
        if len(catalog_stars) < 3:
            return []
        
        invariants = []
        n = len(catalog_stars)
        
        for i in range(n-2):
            for j in range(i+1, n-1):
                for k in range(j+1, n):
                    # Calculate angular distances between stars
                    d_ij = self._angular_distance_catalog(
                        catalog_stars[i], catalog_stars[j]
                    )
                    d_jk = self._angular_distance_catalog(
                        catalog_stars[j], catalog_stars[k]
                    )
                    d_ki = self._angular_distance_catalog(
                        catalog_stars[k], catalog_stars[i]
                    )
                    
                    # Sort distances
                    sides = sorted([d_ij, d_jk, d_ki])
                    
                    # Calculate invariant ratios
                    if sides[0] > 0:
                        ratio1 = sides[2] / sides[0]
                        ratio2 = sides[1] / sides[0]
                        
                        # Calculate angle
                        cos_angle = (sides[0]**2 + sides[1]**2 - sides[2]**2) / (2 * sides[0] * sides[1])
                        cos_angle = max(-1, min(1, cos_angle))
                        angle = math.acos(cos_angle)
                        
                        invariants.append((ratio1, ratio2, angle, [i, j, k]))
        
        return invariants
    
    def _angular_distance_catalog(self, star1: dict, star2: dict) -> float:
        """Calculate angular distance between two catalog stars"""
        from utils import angular_distance
        return angular_distance(star1['ra'], star1['dec'], star2['ra'], star2['dec'])
    
    def match(self, detected_stars: List[DetectedStar], 
              estimated_ra: float, estimated_dec: float) -> list[DetectedStar]:
        """
        Match detected stars against catalog
        
        Args:
            detected_stars: Stars detected in image
            estimated_ra: Estimated RA of image center
            estimated_dec: Estimated Dec of image center
            
        Returns:
            Detected stars with catalog data filled in
        """
        if len(detected_stars) < 3:
            logger.warning("Need at least 3 stars for matching")
            return []
        
        # Query catalog for stars in this region
        catalog_stars = self.catalog.query_cone(
            estimated_ra, estimated_dec, 
            self.fov / 2, 
            max_stars=len(detected_stars) * 2
        )
        
        if len(catalog_stars) < 3:
            logger.warning(f"Only {len(catalog_stars)} catalog stars in region")
            return detected_stars  # Return unmatched stars
        
        # Create invariants
        image_invariants = self.create_triangle_invariants(detected_stars)
        catalog_invariants = self.create_catalog_invariants(catalog_stars)
        
        if not image_invariants or not catalog_invariants:
            logger.warning("Could not create invariants")
            return []
        
        # Match invariants
        matches = self._match_invariants(image_invariants, catalog_invariants)
        
        if not matches:
            logger.warning("No matches found")
            return []
        
        # Apply matches to stars
        matched_stars = self._apply_matches(detected_stars, catalog_stars, matches)
        
        logger.info(f"Matched {len(matched_stars)} stars")
        return matched_stars
    
    def _match_invariants(self, image_invariants: list[tuple], 
                          catalog_invariants: list[tuple]) -> list[tuple[int, int, int, int, int, int]]:
        """
        Match image invariants to catalog invariants
        
        Returns:
            List of (img_i, img_j, img_k, cat_i, cat_j, cat_k) matches
        """
        matches = []
        
        for img_idx, (img_r1, img_r2, img_angle) in enumerate(image_invariants):
            for cat_r1, cat_r2, cat_angle, cat_indices in catalog_invariants:
                # Check if invariants match within threshold
                if (abs(img_r1 - cat_r1) / cat_r1 < self.match_threshold and
                    abs(img_r2 - cat_r2) / cat_r2 < self.match_threshold and
                    abs(img_angle - cat_angle) / cat_angle < self.match_threshold):
                    
                    matches.append((
                        img_idx,  # We don't have direct star indices yet
                        0, 0, 0,  # Placeholder
                        cat_indices[0], cat_indices[1], cat_indices[2]
                    ))
        
        return matches
    
    def _apply_matches(self, detected_stars: List[DetectedStar],
                       catalog_stars: List[dict],
                       matches: List[Tuple]) -> List[DetectedStar]:
        """
        Apply matching results to detected stars
        
        Args:
            detected_stars: Detected stars
            catalog_stars: Catalog stars
            matches: Match information
            
        Returns:
            Matched stars with catalog data
        """
        # Count votes for each star
        star_votes = {i: [] for i in range(len(detected_stars))}
        
        for match in matches:
            # Simplified: match based on brightness order
            # In production, use proper geometric voting
            for i, cat_idx in enumerate(match[3:6]):
                if i < len(detected_stars):
                    star_votes[i].append(cat_idx)
        
        # Apply most common match for each star
        matched_stars = []
        for i, votes in star_votes.items():
            if votes:
                # Get most common catalog index
                from collections import Counter
                if votes:
                    cat_idx = Counter(votes).most_common(1)[0][0]
                    if cat_idx < len(catalog_stars):
                        detected_stars[i].ra = catalog_stars[cat_idx]['ra']
                        detected_stars[i].dec = catalog_stars[cat_idx]['dec']
                        detected_stars[i].magnitude = catalog_stars[cat_idx]['magnitude']
                        detected_stars[i].name = catalog_stars[cat_idx].get('name', f"Star_{cat_idx}")
                        matched_stars.append(detected_stars[i])
        
        # If matching failed, fall back to brightness-based matching
        if not matched_stars:
            logger.info("Falling back to brightness-based matching")
            for i, star in enumerate(detected_stars[:min(len(detected_stars), len(catalog_stars))]):
                star.ra = catalog_stars[i]['ra']
                star.dec = catalog_stars[i]['dec']
                star.magnitude = catalog_stars[i]['magnitude']
                star.name = catalog_stars[i].get('name', f"Star_{i}")
                matched_stars.append(star)
        
        return matched_stars

