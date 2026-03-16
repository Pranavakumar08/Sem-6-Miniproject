"""
TARAPATH - System Tests
"""

import unittest
import numpy as np
import cv2
import os
import tempfile
from datetime import datetime

from star_catalog import StarCatalog
from star_detector import StarDetector
from pattern_matcher import PatternMatcher
from position_solver import PositionSolver
from imu_handler import IMUHandler
from tarapath_core import TARAPATH
import utils

class TestStarCatalog(unittest.TestCase):
    """Test star catalog functionality"""
    
    @classmethod
    def setUpClass(cls):
        cls.catalog = StarCatalog(catalog_path="./test_catalog")
    
    def test_catalog_loading(self):
        """Test that catalog loads"""
        self.assertIsNotNone(self.catalog.stars_df)
        self.assertTrue(len(self.catalog.stars_df) > 0)
    
    def test_cone_query(self):
        """Test cone search"""
        # Query around Polaris
        stars = self.catalog.query_cone(37.95, 89.26, 5.0, max_stars=10)
        self.assertIsInstance(stars, list)
        self.assertTrue(len(stars) <= 10)
        
        if len(stars) > 0:
            star = stars[0]
            self.assertIn('ra', star)
            self.assertIn('dec', star)
            self.assertIn('magnitude', star)
    
    def test_brightest_stars(self):
        """Test getting brightest stars"""
        stars = self.catalog.get_brightest_stars(5)
        self.assertEqual(len(stars), 5)
        
        # Check they're sorted by magnitude
        magnitudes = [s['magnitude'] for s in stars]
        self.assertEqual(magnitudes, sorted(magnitudes))

class TestStarDetector(unittest.TestCase):
    """Test star detection functionality"""
    
    def setUp(self):
        self.detector = StarDetector(threshold=30, min_area=3)
        self.test_image = utils.create_test_image(num_stars=20)
    
    def test_detection(self):
        """Test star detection"""
        stars = self.detector.detect(self.test_image)
        self.assertIsInstance(stars, list)
        self.assertTrue(len(stars) > 0)
        
        if len(stars) > 0:
            star = stars[0]
            self.assertIsNotNone(star.x)
            self.assertIsNotNone(star.y)
            self.assertIsNotNone(star.intensity)
    
    def test_detection_with_confidence(self):
        """Test detection with confidence scores"""
        results = self.detector.detect_with_confidence(self.test_image)
        self.assertIsInstance(results, list)
        
        if len(results) > 0:
            star, confidence = results[0]
            self.assertIsInstance(star, DetectedStar)
            self.assertIsInstance(confidence, float)
            self.assertTrue(0 <= confidence <= 1)

class TestIMUHandler(unittest.TestCase):
    """Test IMU handler functionality"""
    
    def setUp(self):
        self.imu = IMUHandler(use_simulation=True)
    
    def test_read_sensors(self):
        """Test sensor reading"""
        data = self.imu.read_sensors()
        self.assertIsNotNone(data.pitch)
        self.assertIsNotNone(data.roll)
        self.assertIsNotNone(data.yaw)
        self.assertIsNotNone(data.timestamp)
    
    def test_calibration(self):
        """Test IMU calibration"""
        self.imu.calibrate(duration_seconds=1.0)
        self.assertTrue(self.imu.is_calibrated)
    
    def test_orientation_matrix(self):
        """Test orientation matrix calculation"""
        R = self.imu.get_orientation_matrix()
        self.assertEqual(R.shape, (3, 3))
        
        # Should be orthogonal
        self.assertTrue(np.allclose(R @ R.T, np.eye(3), atol=1e-6))

class TestPositionSolver(unittest.TestCase):
    """Test position solver functionality"""
    
    def setUp(self):
        self.solver = PositionSolver()
        
        # Create mock stars
        from star_detector import DetectedStar
        self.stars = [
            DetectedStar(x=500, y=500, intensity=200, area=5, peak_intensity=255,
                        ra=37.95, dec=89.26, magnitude=2.0),  # Polaris
            DetectedStar(x=400, y=450, intensity=180, area=4, peak_intensity=240,
                        ra=279.23, dec=38.78, magnitude=0.03),  # Vega
            DetectedStar(x=600, y=550, intensity=190, area=5, peak_intensity=250,
                        ra=213.92, dec=19.18, magnitude=-0.05),  # Arcturus
        ]
    
    def test_solve(self):
        """Test position solving"""
        timestamp = datetime.now()
        image_center = (640, 480)
        focal_length = 1000
        
        position = self.solver.solve(
            self.stars, timestamp, image_center, focal_length
        )
        
        self.assertIsNotNone(position)
        self.assertIsInstance(position.latitude, float)
        self.assertIsInstance(position.longitude, float)
        self.assertTrue(0 <= position.confidence <= 1)

class TestTARAPATH(unittest.TestCase):
    """Test complete TARAPATH system"""
    
    def setUp(self):
        self.nav = TARAPATH()
        self.test_image_path = "test_image.jpg"
        self.test_image = utils.create_test_image()
        cv2.imwrite(self.test_image_path, self.test_image)
    
    def tearDown(self):
        if os.path.exists(self.test_image_path):
            os.remove(self.test_image_path)
    
    def test_process_image(self):
        """Test full image processing pipeline"""
        timestamp = datetime.now()
        position = self.nav.process_image(
            self.test_image_path, timestamp, use_imu=True
        )
        
        # Should at least run without errors
        self.assertIsNotNone(position)
    
    def test_visualization(self):
        """Test visualization"""
        self.nav.process_image(self.test_image_path, datetime.now())
        
        with tempfile.NamedTemporaryFile(suffix='.jpg') as tmp:
            self.nav.visualize_results(self.test_image_path, tmp.name)
            self.assertTrue(os.path.exists(tmp.name))
            self.assertTrue(os.path.getsize(tmp.name) > 0)

class TestUtils(unittest.TestCase):
    """Test utility functions"""
    
    def test_angular_distance(self):
        """Test angular distance calculation"""
        # Same point
        dist = utils.angular_distance(0, 0, 0, 0)
        self.assertAlmostEqual(dist, 0)
        
        # 90 degrees apart
        dist = utils.angular_distance(0, 0, 90, 0)
        self.assertAlmostEqual(dist, 90, places=5)
        
        # 180 degrees apart
        dist = utils.angular_distance(0, 0, 180, 0)
        self.assertAlmostEqual(dist, 180, places=5)
    
    def test_pixel_angle_conversion(self):
        """Test pixel to angle conversion"""
        x, y = 500, 500
        cx, cy = 640, 480
        focal = 1000
        
        theta_x, theta_y = utils.pixel_to_angle(x, y, cx, cy, focal)
        x2, y2 = utils.angle_to_pixel(theta_x, theta_y, cx, cy, focal)
        
        self.assertAlmostEqual(x, x2, places=5)
        self.assertAlmostEqual(y, y2, places=5)
    
    def test_sidereal_time(self):
        """Test sidereal time calculation"""
        timestamp = datetime(2024, 3, 15, 0, 0, 0)
        lst = utils.calculate_sidereal_time(timestamp)
        self.assertIsInstance(lst, float)
        self.assertTrue(0 <= lst < 360)

if __name__ == '__main__':
    unittest.main()

