"""
TARAPATH - Configuration Settings
"""

from dataclasses import dataclass, field
from typing import Tuple

@dataclass
class CameraConfig:
    """Camera configuration"""
    focal_length_px: float = 1200.0  # Focal length in pixels
    sensor_width_px: int = 4032       # Sensor width in pixels
    sensor_height_px: int = 3024      # Sensor height in pixels
    pixel_size_um: float = 1.4        # Pixel size in micrometers
    fov_deg: float = 45.0             # Field of view in degrees
    
    @property
    def center(self) -> Tuple[float, float]:
        """Get image center coordinates"""
        return (self.sensor_width_px / 2, self.sensor_height_px / 2)

@dataclass
class DetectionConfig:
    """Star detection configuration"""
    threshold: int = 30           # Detection threshold (0-255)
    min_area: int = 3             # Minimum pixel area for a star
    max_stars: int = 50           # Maximum stars to detect
    use_gpu: bool = False         # Use GPU acceleration
    blur_kernel: int = 5          # Gaussian blur kernel size

@dataclass
class CatalogConfig:
    """Star catalog configuration"""
    max_magnitude: float = 6.0     # Maximum star magnitude (6.0 = naked eye limit)
    catalog_path: str = "./data/star_catalog"
    auto_update: bool = False      # Auto-update catalog
    cache_size: int = 1000         # Cache size for queries

@dataclass
class NavigationConfig:
    """Navigation configuration"""
    min_stars_for_solution: int = 3
    max_iterations: int = 10
    convergence_tolerance: float = 1e-6
    confidence_threshold: float = 0.7

@dataclass
class IMUConfig:
    """IMU configuration"""
    calibration_samples: int = 100
    update_rate_hz: int = 100
    use_filter: bool = True
    filter_alpha: float = 0.8      # Complementary filter coefficient

@dataclass
class TARAPATHConfig:
    """Main configuration"""
    # Use default_factory for mutable defaults
    camera: CameraConfig = field(default_factory=CameraConfig)
    detection: DetectionConfig = field(default_factory=DetectionConfig)
    catalog: CatalogConfig = field(default_factory=CatalogConfig)
    navigation: NavigationConfig = field(default_factory=NavigationConfig)
    imu: IMUConfig = field(default_factory=IMUConfig)
    
    # System settings
    debug_mode: bool = False
    log_level: str = "INFO"
    save_results: bool = True
    results_path: str = "./results"

# Global configuration instance
config = TARAPATHConfig()