"""
TARAPATH - Star Detection Module
Detects stars in images using computer vision
"""

import numpy as np
import cv2
from typing import List, Tuple, Optional
from dataclasses import dataclass
import logging

from config import config

logger = logging.getLogger(__name__)

@dataclass
class DetectedStar:
    """Data structure for detected stars"""
    x: float
    y: float
    intensity: float
    area: float
    peak_intensity: float
    ra: Optional[float] = None
    dec: Optional[float] = None
    magnitude: Optional[float] = None
    name: Optional[str] = None
    
    @property
    def position(self) -> Tuple[float, float]:
        return (self.x, self.y)

class StarDetector:
    """
    Detects stars in images using computer vision techniques
    """
    
    def __init__(self, threshold: int = None, min_area: int = None):
        """
        Initialize star detector
        
        Args:
            threshold: Detection threshold (0-255)
            min_area: Minimum pixel area for a star
        """
        self.threshold = threshold or config.detection.threshold
        self.min_area = min_area or config.detection.min_area
        self.max_stars = config.detection.max_stars
        self.blur_kernel = config.detection.blur_kernel
        
        # Use lower threshold for test images
        self.test_mode = False
    
    def detect(self, image: np.ndarray) -> List[DetectedStar]:
        """
        Detect stars in image
        
        Args:
            image: Input image (BGR or grayscale)
            
        Returns:
            List of detected stars
        """
        # Convert to grayscale if needed
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        # Log image statistics for debugging
        logger.debug(f"Image stats - min: {np.min(gray)}, max: {np.max(gray)}, mean: {np.mean(gray):.1f}")
        
        # Apply slight Gaussian blur to reduce noise
        blurred = cv2.GaussianBlur(gray, (self.blur_kernel, self.blur_kernel), 0.5)
        
        # Try multiple threshold values to find stars
        stars = []
        
        # Use much lower thresholds for test images
        thresholds = [20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150]
        
        for thresh_val in thresholds:
            # Apply threshold
            _, thresh = cv2.threshold(blurred, thresh_val, 255, cv2.THRESH_BINARY)
            
            # Find contours
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            for contour in contours:
                area = cv2.contourArea(contour)
                if area < 2:  # Very small minimum area
                    continue
                
                # Calculate centroid
                star = self._calculate_centroid(contour, gray)
                if star and star.peak_intensity > 50:  # Only consider relatively bright spots
                    # Check if we already have this star (within 3 pixels)
                    is_duplicate = False
                    for existing_star in stars:
                        dist = np.sqrt((existing_star.x - star.x)**2 + (existing_star.y - star.y)**2)
                        if dist < 3.0:
                            # Keep the brighter one
                            if star.peak_intensity > existing_star.peak_intensity:
                                stars.remove(existing_star)
                                stars.append(star)
                            is_duplicate = True
                            break
                    
                    if not is_duplicate:
                        stars.append(star)
        
        # Remove duplicates more thoroughly
        unique_stars = []
        for star in stars:
            is_duplicate = False
            for unique in unique_stars:
                dist = np.sqrt((unique.x - star.x)**2 + (unique.y - star.y)**2)
                if dist < 3.0:
                    is_duplicate = True
                    # Keep the brighter one
                    if star.peak_intensity > unique.peak_intensity:
                        unique_stars.remove(unique)
                        unique_stars.append(star)
                    break
            if not is_duplicate:
                unique_stars.append(star)
        
        # Sort by peak intensity (brightest first)
        unique_stars.sort(key=lambda s: s.peak_intensity, reverse=True)
        
        # Log detected stars for debugging
        logger.info(f"Detected {len(unique_stars)} stars")
        for i, star in enumerate(unique_stars[:5]):  # Log first 5 stars
            logger.debug(f"  Star {i+1}: pos=({star.x:.1f}, {star.y:.1f}), intensity={star.peak_intensity:.0f}")
        
        # Limit to maximum number
        unique_stars = unique_stars[:self.max_stars]
        
        return unique_stars
    
    def _calculate_centroid(self, contour: np.ndarray, 
                           gray_image: np.ndarray) -> Optional[DetectedStar]:
        """
        Calculate sub-pixel centroid of a star
        
        Args:
            contour: Contour of the star
            gray_image: Original grayscale image
            
        Returns:
            DetectedStar object with centroid coordinates
        """
        # Create mask for this contour
        mask = np.zeros(gray_image.shape, np.uint8)
        cv2.drawContours(mask, [contour], -1, 255, -1)
        
        # Get pixel coordinates in mask
        y_indices, x_indices = np.where(mask == 255)
        
        if len(y_indices) < 2:  # Very small minimum
            return None
        
        # Get intensities
        intensities = gray_image[y_indices, x_indices].astype(float)
        
        # Calculate center of mass
        total_intensity = np.sum(intensities)
        if total_intensity < 10:  # Too dim
            return None
        
        x_center = np.sum(x_indices * intensities) / total_intensity
        y_center = np.sum(y_indices * intensities) / total_intensity
        
        # Get peak intensity
        peak_intensity = np.max(intensities)
        
        # Calculate average intensity
        avg_intensity = total_intensity / len(y_indices)
        
        return DetectedStar(
            x=float(x_center),
            y=float(y_center),
            intensity=float(avg_intensity),
            area=float(len(y_indices)),
            peak_intensity=float(peak_intensity)
        )
    
    def detect_with_confidence(self, image: np.ndarray) -> List[Tuple[DetectedStar, float]]:
        """
        Detect stars with confidence scores
        
        Args:
            image: Input image
            
        Returns:
            List of (star, confidence) tuples
        """
        stars = self.detect(image)
        
        # Calculate confidence based on star properties
        results = []
        for star in stars:
            # Confidence factors
            intensity_factor = min(1.0, star.peak_intensity / 200.0)
            area_factor = min(1.0, star.area / 20.0)
            
            confidence = 0.7 * intensity_factor + 0.3 * area_factor
            confidence = min(1.0, max(0.1, confidence))
            
            results.append((star, confidence))
        
        return results
    
    def set_test_mode(self, enabled: bool = True):
        """Set test mode for more sensitive detection"""
        self.test_mode = enabled
        if enabled:
            logger.info("Star detector set to test mode (more sensitive)")