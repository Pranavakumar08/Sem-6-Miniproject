"""
TARAPATH - Core Navigation System
Integrates all components into a complete offline celestial navigation system
"""

import cv2
import numpy as np
from datetime import datetime
from typing import Optional, List, Tuple
import logging

from config import config
from star_catalog import StarCatalog
from star_detector import StarDetector, DetectedStar
from pattern_matcher import PatternMatcher
from position_solver import PositionSolver, Position
from imu_handler import IMUHandler
import utils

logger = logging.getLogger(__name__)

class TARAPATH:
    """
    Main TARAPATH navigation system
    Integrates all components for complete offline celestial navigation
    """
    
    # In tarapath_core.py, modify the __init__ method:

    def __init__(self, config_override: dict = None, test_mode: bool = False):
        """
        Initialize TARAPATH system
        
        Args:
            config_override: Optional configuration overrides
            test_mode: Enable test mode with more sensitive detection
        """
        # Update config if overrides provided
        if config_override:
            for key, value in config_override.items():
                if hasattr(config, key):
                    setattr(config, key, value)
        
        logger.info("Initializing TARAPATH navigation system...")
        
        # Initialize components
        self.catalog = StarCatalog()
        self.detector = StarDetector()
        
        # Set test mode if requested
        if test_mode:
            self.detector.set_test_mode(True)
        
        self.matcher = PatternMatcher(self.catalog, config.camera.fov_deg)
        self.solver = PositionSolver()
        self.imu = IMUHandler(use_simulation=True)
        
        # Calibrate IMU
        self.imu.calibrate(duration_seconds=2.0)
        
        # State
        self.last_position = None
        self.detected_stars = []
        self.matched_stars = []
        
        logger.info("TARAPATH initialized successfully")
    
    def process_image(self, image_path: str, timestamp: datetime = None,
                     use_imu: bool = True) -> Optional[Position]:
        """
        Process a night sky image to determine position
        
        Args:
            image_path: Path to image file
            timestamp: Time of capture (if None, uses file modification time)
            use_imu: Whether to use IMU for orientation correction
            
        Returns:
            Estimated position or None if failed
        """
        # Load image
        logger.info(f"Loading image: {image_path}")
        image = cv2.imread(image_path)
        if image is None:
            logger.error(f"Failed to load image: {image_path}")
            return None
        
        h, w = image.shape[:2]
        image_center = (w/2, h/2)
        
        # Get timestamp
        if timestamp is None:
            import os
            mtime = os.path.getmtime(image_path)
            timestamp = datetime.fromtimestamp(mtime)
        
        # Get IMU orientation if requested
        camera_tilt = (0, 0)
        if use_imu:
            imu_data = self.imu.read_sensors()
            camera_tilt = (imu_data.pitch, imu_data.roll)
            logger.debug(f"IMU orientation: pitch={imu_data.pitch:.2f}°, roll={imu_data.roll:.2f}°")
        
        # Step 1: Detect stars
        logger.info("Detecting stars...")
        self.detected_stars = self.detector.detect(image)
        logger.info(f"Detected {len(self.detected_stars)} stars")
        
        if len(self.detected_stars) < config.navigation.min_stars_for_solution:
            logger.error(f"Insufficient stars detected (need {config.navigation.min_stars_for_solution})")
            return None
        
        # Step 2: Estimate sky region based on time
        # At local midnight, RA ~ LST
        lst = utils.calculate_sidereal_time(timestamp, 0)  # Use GST initially
        estimated_ra = lst
        estimated_dec = 45  # Assume mid-latitude initially
        
        # Step 3: Match star patterns
        logger.info("Matching star patterns...")
        self.matched_stars = self.matcher.match(self.detected_stars, estimated_ra, estimated_dec)
        logger.info(f"Matched {len(self.matched_stars)} stars")
        
        if len(self.matched_stars) < config.navigation.min_stars_for_solution:
            logger.error("Insufficient star matches")
            return None
        
        # Step 4: Solve for position
        logger.info("Solving for position...")
        position = self.solver.solve(
            self.matched_stars, 
            timestamp,
            image_center,
            config.camera.focal_length_px,
            camera_tilt
        )
        
        if position:
            logger.info(f"Position found: {position.latitude:.4f}°N, {position.longitude:.4f}°E")
            logger.info(f"Confidence: {position.confidence:.1%}")
            self.last_position = position
        
        return position
    
    def process_image_array(self, image: np.ndarray, timestamp: datetime = None,
                           use_imu: bool = True) -> Optional[Position]:
        """
        Process a night sky image array to determine position
        
        Args:
            image: Image as numpy array
            timestamp: Time of capture
            use_imu: Whether to use IMU for orientation correction
            
        Returns:
            Estimated position or None if failed
        """
        h, w = image.shape[:2]
        image_center = (w/2, h/2)
        
        if timestamp is None:
            timestamp = datetime.now()
        
        # Get IMU orientation if requested
        camera_tilt = (0, 0)
        if use_imu:
            imu_data = self.imu.read_sensors()
            camera_tilt = (imu_data.pitch, imu_data.roll)
        
        # Detect stars
        self.detected_stars = self.detector.detect(image)
        
        if len(self.detected_stars) < config.navigation.min_stars_for_solution:
            return None
        
        # Estimate sky region
        lst = utils.calculate_sidereal_time(timestamp, 0)
        estimated_ra = lst
        estimated_dec = 45
        
        # Match stars
        self.matched_stars = self.matcher.match(self.detected_stars, estimated_ra, estimated_dec)
        
        if len(self.matched_stars) < config.navigation.min_stars_for_solution:
            return None
        
        # Solve for position
        position = self.solver.solve(
            self.matched_stars,
            timestamp,
            image_center,
            config.camera.focal_length_px,
            camera_tilt
        )
        
        if position:
            self.last_position = position
        
        return position
    
    def visualize_results(self, image_path: str, output_path: str = None):
        """
        Create visualization of results
        
        Args:
            image_path: Path to original image
            output_path: Path to save visualization (if None, displays)
        """
        if self.last_position is None:
            logger.warning("No position to visualize")
            return
        
        image = cv2.imread(image_path)
        
        # Draw detected stars
        for star in self.detected_stars:
            color = (0, 255, 0) if star.ra is not None else (0, 0, 255)
            cv2.circle(image, (int(star.x), int(star.y)), 5, color, 2)
            
            if star.name:
                cv2.putText(image, star.name, (int(star.x)+10, int(star.y)),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        
        # Add position info
        info = [
            f"Latitude: {self.last_position.latitude:.6f}°",
            f"Longitude: {self.last_position.longitude:.6f}°",
            f"Confidence: {self.last_position.confidence:.1%}",
            f"Error: {self.last_position.error_radius:.0f}m",
            f"Stars: {len(self.matched_stars)}/{len(self.detected_stars)}"
        ]
        
        y = 30
        for text in info:
            cv2.putText(image, text, (10, y), cv2.FONT_HERSHEY_SIMPLEX,
                       0.6, (0, 255, 255), 2)
            y += 25
        
        # Add timestamp
        timestamp = self.last_position.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")
        cv2.putText(image, timestamp, (10, y+10), cv2.FONT_HERSHEY_SIMPLEX,
                   0.5, (255, 255, 255), 1)
        
        if output_path:
            cv2.imwrite(output_path, image)
            logger.info(f"Visualization saved to {output_path}")
        else:
            cv2.imshow("TARAPATH Results", image)
            cv2.waitKey(0)
            cv2.destroyAllWindows()
    
    def save_state(self, filepath: str):
        """Save system state to file"""
        import pickle
        
        state = {
            'last_position': self.last_position,
            'detected_stars': self.detected_stars,
            'matched_stars': self.matched_stars,
            'timestamp': datetime.now()
        }
        
        with open(filepath, 'wb') as f:
            pickle.dump(state, f)
        
        logger.info(f"State saved to {filepath}")
    
    def load_state(self, filepath: str):
        """Load system state from file"""
        import pickle
        
        with open(filepath, 'rb') as f:
            state = pickle.load(f)
        
        self.last_position = state['last_position']
        self.detected_stars = state['detected_stars']
        self.matched_stars = state['matched_stars']
        
        logger.info(f"State loaded from {filepath}")

