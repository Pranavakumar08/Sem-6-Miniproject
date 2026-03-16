"""
TARAPATH - Utility Functions
"""

import numpy as np
import cv2
from datetime import datetime
import json
import os
import logging
from typing import Dict, Any, Optional
import math

logger = logging.getLogger(__name__)

def setup_logging(log_level: str = "INFO", log_file: Optional[str] = None):
    """
    Setup logging configuration
    
    Args:
        log_level: Logging level as string ("DEBUG", "INFO", "WARNING", "ERROR")
        log_file: Optional log file path
    """
    handlers = [logging.StreamHandler()]
    
    # Convert string level to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Only try to create directory and file handler if log_file is provided and not empty
    if log_file:
        log_dir = os.path.dirname(log_file)
        if log_dir:  # Only create directory if there's a path component
            os.makedirs(log_dir, exist_ok=True)
        handlers.append(logging.FileHandler(log_file))
    
    logging.basicConfig(
        level=numeric_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=handlers
    )

def angular_distance(ra1: float, dec1: float, ra2: float, dec2: float) -> float:
    """
    Calculate angular distance between two celestial points
    
    Args:
        ra1, dec1: First point coordinates (degrees)
        ra2, dec2: Second point coordinates (degrees)
    
    Returns:
        Angular distance in degrees
    """
    # Convert to radians
    ra1_r = math.radians(ra1)
    dec1_r = math.radians(dec1)
    ra2_r = math.radians(ra2)
    dec2_r = math.radians(dec2)
    
    # Haversine formula
    d_ra = ra2_r - ra1_r
    d_dec = dec2_r - dec1_r
    
    a = math.sin(d_dec/2)**2 + math.cos(dec1_r) * math.cos(dec2_r) * math.sin(d_ra/2)**2
    # Ensure a is within valid range due to floating point errors
    a = max(0, min(1, a))
    c = 2 * math.asin(math.sqrt(a))
    
    return math.degrees(c)

def pixel_to_angle(x: float, y: float, center_x: float, center_y: float, 
                   focal_length: float) -> tuple[float, float]:
    """
    Convert pixel coordinates to angular coordinates
    
    Args:
        x, y: Pixel coordinates
        center_x, center_y: Image center
        focal_length: Focal length in pixels
    
    Returns:
        (theta_x, theta_y) in radians
    """
    dx = x - center_x
    dy = y - center_y
    
    theta_x = math.atan2(dx, focal_length)
    theta_y = math.atan2(dy, focal_length)
    
    return theta_x, theta_y

def angle_to_pixel(theta_x: float, theta_y: float, center_x: float, center_y: float,
                   focal_length: float) -> tuple[float, float]:
    """
    Convert angular coordinates to pixel coordinates
    
    Args:
        theta_x, theta_y: Angular coordinates (radians)
        center_x, center_y: Image center
        focal_length: Focal length in pixels
    
    Returns:
        (x, y) pixel coordinates
    """
    x = center_x + focal_length * math.tan(theta_x)
    y = center_y + focal_length * math.tan(theta_y)
    
    return x, y

def save_results(results: dict[str, Any], filename: str):
    """Save results to JSON file"""
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    
    # Convert datetime to string if present
    if 'timestamp' in results and isinstance(results['timestamp'], datetime):
        results['timestamp'] = results['timestamp'].isoformat()
    
    with open(filename, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    logger.info(f"Results saved to {filename}")

def load_results(filename: str) -> dict[str, Any]:
    """Load results from JSON file"""
    with open(filename, 'r') as f:
        results = json.load(f)
    
    # Convert string back to datetime
    if 'timestamp' in results:
        try:
            results['timestamp'] = datetime.fromisoformat(results['timestamp'])
        except (ValueError, TypeError):
            pass
    
    return results

def create_test_image(num_stars: int = 50, width: int = 1024, height: int = 1024,
                      add_noise: bool = True) -> np.ndarray:
    """
    Create a synthetic star field for testing
    
    Args:
        num_stars: Number of stars to generate
        width, height: Image dimensions
        add_noise: Add Gaussian noise
    
    Returns:
        Test image as numpy array
    """
    # Start with a pure black image
    image = np.zeros((height, width, 3), dtype=np.uint8)
    
    # Generate stars with much higher contrast
    np.random.seed(42)  # For reproducibility
    
    # Add stars with realistic brightness distribution
    for i in range(num_stars):
        x = np.random.randint(0, width)
        y = np.random.randint(0, height)
        
        # Make stars much brighter - use higher intensity values
        # Random brightness with some very bright stars
        brightness_choice = np.random.choice(['dim', 'medium', 'bright', 'very_bright'], 
                                            p=[0.2, 0.3, 0.3, 0.2])
        
        if brightness_choice == 'dim':
            brightness = np.random.randint(180, 200)
            size = 2
        elif brightness_choice == 'medium':
            brightness = np.random.randint(200, 220)
            size = 3
        elif brightness_choice == 'bright':
            brightness = np.random.randint(220, 240)
            size = 4
        else:  # very_bright
            brightness = np.random.randint(240, 255)
            size = 5
        
        # Draw star as a filled circle
        cv2.circle(image, (x, y), size, (brightness, brightness, brightness), -1)
        
        # Add a brighter core for larger stars
        if size >= 4:
            cv2.circle(image, (x, y), size-2, (255, 255, 255), -1)
    
    # Apply slight Gaussian blur to blend stars
    image = cv2.GaussianBlur(image, (3, 3), 0.5)
    
    # Add minimal noise
    if add_noise:
        noise = np.random.normal(0, 2, image.shape).astype(np.uint8)
        image = cv2.add(image, noise)
    
    # Ensure values are in valid range
    image = np.clip(image, 0, 255).astype(np.uint8)
    
    # Save a copy for verification
    cv2.imwrite("debug_test_image.jpg", image)
    print(f"Debug: Test image saved with max brightness: {np.max(image)}")
    
    return image

def calculate_sidereal_time(timestamp: datetime, longitude: float = 0) -> float:
    """
    Calculate Local Sidereal Time (simplified)
    
    Args:
        timestamp: UTC timestamp
        longitude: Observer longitude (degrees, east positive)
    
    Returns:
        Local Sidereal Time in degrees
    """
    # Julian Date relative to J2000 (simplified)
    j2000 = datetime(2000, 1, 1, 12, 0, 0)
    days_since_j2000 = (timestamp - j2000).total_seconds() / 86400.0
    
    # GST approximation (degrees)
    # Formula: GST = 100.46 + 0.985647 * days_since_J2000 + 15 * UT_hours
    ut_hours = timestamp.hour + timestamp.minute/60.0 + timestamp.second/3600.0
    gst_deg = (100.46 + 0.985647 * days_since_j2000 + 15 * ut_hours) % 360
    
    # Convert to LST
    lst_deg = (gst_deg + longitude) % 360
    
    return lst_deg