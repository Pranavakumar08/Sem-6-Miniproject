"""
TARAPATH - Position Calculation
Calculates geographic position from celestial observations
"""

import numpy as np
import math
from datetime import datetime, timedelta
from typing import List, Tuple, Optional
from dataclasses import dataclass
import logging

from star_detector import DetectedStar
from utils import calculate_sidereal_time
from config import config

logger = logging.getLogger(__name__)

@dataclass
class Sight:
    """Single celestial sight"""
    star: DetectedStar
    altitude: float  # Observed altitude (degrees)
    azimuth: float   # Observed azimuth (degrees)
    timestamp: datetime
    weight: float = 1.0

@dataclass
class Position:
    """Calculated geographic position"""
    latitude: float
    longitude: float
    confidence: float
    error_radius: float  # meters
    num_stars_used: int
    residuals: List[float]
    timestamp: datetime

class PositionSolver:
    """
    Solves for geographic position using celestial navigation
    Implements full spherical trigonometry
    """
    
    def __init__(self):
        """Initialize position solver"""
        self.earth_radius_km = 6371.0
        self.min_stars = config.navigation.min_stars_for_solution
        self.max_iterations = config.navigation.max_iterations
        self.tolerance = config.navigation.convergence_tolerance
    
    def calculate_altitude_azimuth(self, star: DetectedStar,
                                   image_center: Tuple[float, float],
                                   focal_length: float,
                                   camera_tilt: Tuple[float, float] = (0, 0)) -> Tuple[float, float]:
        """
        Calculate altitude and azimuth from image coordinates
        
        Args:
            star: Detected star
            image_center: (cx, cy) image center
            focal_length: Camera focal length in pixels
            camera_tilt: (pitch, roll) in degrees
            
        Returns:
            (altitude, azimuth) in degrees
        """
        cx, cy = image_center
        
        # Convert pixel coordinates to angular coordinates
        dx = star.x - cx
        dy = star.y - cy
        
        # Calculate angles from optical axis
        theta_x = math.atan2(dx, focal_length)
        theta_y = math.atan2(dy, focal_length)
        
        # Convert to altitude/azimuth (assuming camera pointed at zenith)
        altitude = 90 - math.degrees(math.sqrt(theta_x**2 + theta_y**2))
        azimuth = math.degrees(math.atan2(dx, -dy)) % 360
        
        # Apply camera tilt correction
        pitch, roll = math.radians(camera_tilt[0]), math.radians(camera_tilt[1])
        
        # Simple tilt correction
        altitude += math.degrees(pitch * math.cos(math.radians(azimuth)) + 
                                 roll * math.sin(math.radians(azimuth)))
        
        return altitude, azimuth
    
    def calculate_expected_altitude(self, latitude: float, longitude: float,
                                   star_ra: float, star_dec: float,
                                   timestamp: datetime) -> float:
        """
        Calculate expected altitude for a given position
        
        Args:
            latitude: Observer latitude (degrees)
            longitude: Observer longitude (degrees)
            star_ra: Star Right Ascension (degrees)
            star_dec: Star Declination (degrees)
            timestamp: Observation time
            
        Returns:
            Expected altitude (degrees)
        """
        # Calculate Local Sidereal Time
        lst = calculate_sidereal_time(timestamp, longitude)
        
        # Calculate Hour Angle
        ha = (lst - star_ra) % 360
        if ha > 180:
            ha -= 360
        ha_rad = math.radians(ha)
        
        # Convert to radians
        lat_rad = math.radians(latitude)
        dec_rad = math.radians(star_dec)
        
        # Calculate altitude using spherical trigonometry
        # sin(alt) = sin(lat) * sin(dec) + cos(lat) * cos(dec) * cos(HA)
        sin_alt = (math.sin(lat_rad) * math.sin(dec_rad) + 
                   math.cos(lat_rad) * math.cos(dec_rad) * math.cos(ha_rad))
        
        # Clamp to valid range
        sin_alt = max(-1, min(1, sin_alt))
        
        return math.degrees(math.asin(sin_alt))
    
    def calculate_azimuth(self, latitude: float, star_dec: float,
                          ha: float, altitude: float) -> float:
        """
        Calculate azimuth for a given position
        
        Args:
            latitude: Observer latitude (degrees)
            star_dec: Star Declination (degrees)
            ha: Hour Angle (degrees)
            altitude: Altitude (degrees)
            
        Returns:
            Azimuth (degrees)
        """
        lat_rad = math.radians(latitude)
        dec_rad = math.radians(star_dec)
        ha_rad = math.radians(ha)
        alt_rad = math.radians(altitude)
        
        # Calculate azimuth using spherical trigonometry
        cos_az = (math.sin(dec_rad) - math.sin(lat_rad) * math.sin(alt_rad)) / \
                 (math.cos(lat_rad) * math.cos(alt_rad))
        
        cos_az = max(-1, min(1, cos_az))
        az = math.degrees(math.acos(cos_az))
        
        # Determine quadrant based on hour angle
        if math.sin(ha_rad) > 0:
            az = 360 - az
        
        return az
    
    def create_sights(self, stars: List[DetectedStar], timestamp: datetime,
                     image_center: Tuple[float, float], focal_length: float,
                     camera_tilt: Tuple[float, float] = (0, 0)) -> List[Sight]:
        """
        Create celestial sights from detected stars
        
        Args:
            stars: List of matched stars
            timestamp: Observation time
            image_center: Image center coordinates
            focal_length: Camera focal length
            camera_tilt: Camera tilt (pitch, roll)
            
        Returns:
            List of Sight objects
        """
        sights = []
        
        for star in stars:
            if star.ra is None or star.dec is None:
                continue
            
            # Calculate observed altitude and azimuth
            alt, az = self.calculate_altitude_azimuth(
                star, image_center, focal_length, camera_tilt
            )
            
            # Calculate weight based on star brightness
            if star.magnitude:
                # Brighter stars (lower magnitude) get higher weight
                weight = 1.0 / (1.0 + star.magnitude / 5.0)
            else:
                weight = 1.0
            
            sights.append(Sight(
                star=star,
                altitude=alt,
                azimuth=az,
                timestamp=timestamp,
                weight=weight
            ))
        
        return sights
    
    def solve_least_squares(self, sights: List[Sight],
                           initial_lat: float, initial_lon: float) -> Tuple[float, float, List[float]]:
        """
        Solve for position using least squares optimization
        
        Args:
            sights: List of celestial sights
            initial_lat: Initial latitude estimate
            initial_lon: Initial longitude estimate
            
        Returns:
            (latitude, longitude, residuals)
        """
        lat = initial_lat
        lon = initial_lon
        n = len(sights)
        
        for iteration in range(self.max_iterations):
            # Build Jacobian matrix and residual vector
            J = np.zeros((n, 2))
            r = np.zeros(n)
            
            for i, sight in enumerate(sights):
                # Calculate expected altitude
                alt_expected = self.calculate_expected_altitude(
                    lat, lon, sight.star.ra, sight.star.dec, sight.timestamp
                )
                
                # Residual
                r[i] = alt_expected - sight.altitude
                
                # Partial derivatives (numerical for simplicity)
                delta = 1e-4
                
                # d(alt)/d(lat)
                alt_lat_plus = self.calculate_expected_altitude(
                    lat + delta, lon, sight.star.ra, sight.star.dec, sight.timestamp
                )
                alt_lat_minus = self.calculate_expected_altitude(
                    lat - delta, lon, sight.star.ra, sight.star.dec, sight.timestamp
                )
                J[i, 0] = (alt_lat_plus - alt_lat_minus) / (2 * delta)
                
                # d(alt)/d(lon)
                alt_lon_plus = self.calculate_expected_altitude(
                    lat, lon + delta, sight.star.ra, sight.star.dec, sight.timestamp
                )
                alt_lon_minus = self.calculate_expected_altitude(
                    lat, lon - delta, sight.star.ra, sight.star.dec, sight.timestamp
                )
                J[i, 1] = (alt_lon_plus - alt_lon_minus) / (2 * delta)
                
                # Apply weights
                J[i, :] *= sight.weight
                r[i] *= sight.weight
            
            # Solve normal equations: (J^T J) dx = -J^T r
            JtJ = J.T @ J
            Jtr = J.T @ r
            
            # Add regularization to avoid singular matrix
            JtJ += np.eye(2) * 1e-6
            
            try:
                dx = np.linalg.solve(JtJ, -Jtr)
            except np.linalg.LinAlgError:
                logger.warning("Singular matrix in least squares")
                break
            
            # Update position
            lat += dx[0]
            lon += dx[1]
            
            # Check convergence
            if np.linalg.norm(dx) < self.tolerance:
                break
        
        return lat, lon, r.tolist()
    
    def solve(self, stars: List[DetectedStar], timestamp: datetime,
             image_center: Tuple[float, float], focal_length: float,
             camera_tilt: Tuple[float, float] = (0, 0)) -> Optional[Position]:
        """
        Solve for geographic position
        
        Args:
            stars: List of matched stars
            timestamp: Observation time
            image_center: Image center coordinates
            focal_length: Camera focal length
            camera_tilt: Camera tilt (pitch, roll)
            
        Returns:
            Position object or None if failed
        """
        if len(stars) < self.min_stars:
            logger.warning(f"Need at least {self.min_stars} stars, got {len(stars)}")
            return None
        
        # Create sights
        sights = self.create_sights(stars, timestamp, image_center, focal_length, camera_tilt)
        
        if len(sights) < self.min_stars:
            logger.warning("Insufficient valid sights")
            return None
        
        # Initial estimate: use brightest star's declination as latitude
        # and RA - GST as longitude
        brightest = min(sights, key=lambda s: s.star.magnitude or 10)
        lst = calculate_sidereal_time(timestamp, 0)  # GST
        initial_lat = brightest.star.dec
        initial_lon = (brightest.star.ra - lst) % 360
        if initial_lon > 180:
            initial_lon -= 360
        
        # Solve using least squares
        lat, lon, residuals = self.solve_least_squares(sights, initial_lat, initial_lon)
        
        # Calculate confidence
        # Factors: number of stars, residual magnitude, star brightness
        star_factor = min(1.0, len(sights) / 10.0)
        residual_factor = 1.0 - min(1.0, np.std(residuals) / 5.0)
        brightness_factor = np.mean([1.0 / (1.0 + s.star.magnitude/5.0) for s in sights])
        
        confidence = 0.4 * star_factor + 0.4 * residual_factor + 0.2 * brightness_factor
        
        # Calculate error radius (simplified)
        # In production, use proper covariance propagation
        error_radius = 1000 * (1.0 - confidence) / confidence if confidence > 0 else 10000
        
        return Position(
            latitude=lat,
            longitude=lon,
            confidence=confidence,
            error_radius=error_radius,
            num_stars_used=len(sights),
            residuals=residuals,
            timestamp=timestamp
        )

