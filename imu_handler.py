"""
TARAPATH - IMU Sensor Integration
Simulates and processes IMU data for camera orientation
"""

import numpy as np
import math
import random
import time
from typing import Tuple, Optional
from dataclasses import dataclass
import logging

from config import config

logger = logging.getLogger(__name__)

@dataclass
class IMUData:
    """IMU sensor data"""
    pitch: float      # degrees
    roll: float       # degrees
    yaw: float        # degrees
    timestamp: float  # seconds
    temperature: float  # Celsius

class IMUHandler:
    """
    Handles IMU sensor data for camera orientation correction
    
    In production, this would interface with actual IMU hardware.
    This version provides simulation and calibration capabilities.
    """
    
    def __init__(self, use_simulation: bool = True):
        """
        Initialize IMU handler
        
        Args:
            use_simulation: If True, use simulated data
        """
        self.use_simulation = use_simulation
        self.calibration_samples = config.imu.calibration_samples
        self.update_rate = config.imu.update_rate_hz
        self.use_filter = config.imu.use_filter
        self.filter_alpha = config.imu.filter_alpha
        
        # Calibration offsets
        self.pitch_offset = 0.0
        self.roll_offset = 0.0
        self.yaw_offset = 0.0
        self.is_calibrated = False
        
        # Filtered values
        self.filtered_pitch = 0.0
        self.filtered_roll = 0.0
        self.filtered_yaw = 0.0
        
        # Last reading time
        self.last_read_time = time.time()
        
        # Simulation parameters
        self.sim_pitch = 0.0
        self.sim_roll = 0.0
        self.sim_yaw = 0.0
        self.sim_drift = 0.001  # degrees per second
        
        logger.info(f"IMU Handler initialized (simulation={use_simulation})")
    
    def read_sensors(self) -> IMUData:
        """
        Read IMU sensors
        
        Returns:
            IMUData object with current readings
        """
        current_time = time.time()
        
        if self.use_simulation:
            pitch, roll, yaw = self._read_simulated()
        else:
            pitch, roll, yaw = self._read_hardware()
        
        # Apply calibration if available
        if self.is_calibrated:
            pitch -= self.pitch_offset
            roll -= self.roll_offset
            yaw -= self.yaw_offset
        
        # Apply low-pass filter
        if self.use_filter:
            dt = current_time - self.last_read_time
            alpha = self.filter_alpha
            
            self.filtered_pitch = alpha * self.filtered_pitch + (1 - alpha) * pitch
            self.filtered_roll = alpha * self.filtered_roll + (1 - alpha) * roll
            self.filtered_yaw = alpha * self.filtered_yaw + (1 - alpha) * yaw
            
            pitch = self.filtered_pitch
            roll = self.filtered_roll
            yaw = self.filtered_yaw
        
        self.last_read_time = current_time
        
        # Simulated temperature (random)
        temperature = 25.0 + random.uniform(-2, 2)
        
        return IMUData(
            pitch=pitch,
            roll=roll,
            yaw=yaw,
            timestamp=current_time,
            temperature=temperature
        )
    
    def _read_hardware(self) -> Tuple[float, float, float]:
        """
        Read from actual IMU hardware
        Placeholder - implement based on your hardware
        """
        # This would interface with actual sensors
        # For now, return simulated data
        return self._read_simulated()
    
    def _read_simulated(self) -> Tuple[float, float, float]:
        """
        Generate simulated IMU data
        
        Returns:
            (pitch, roll, yaw) in degrees
        """
        # Update simulation with some drift and noise
        dt = time.time() - self.last_read_time
        
        # Add slow drift
        self.sim_pitch += self.sim_drift * dt * random.uniform(-1, 1)
        self.sim_roll += self.sim_drift * dt * random.uniform(-1, 1)
        self.sim_yaw += self.sim_drift * dt * random.uniform(-1, 1)
        
        # Add noise
        pitch_noise = random.gauss(0, 0.1)
        roll_noise = random.gauss(0, 0.1)
        yaw_noise = random.gauss(0, 0.05)
        
        return (
            self.sim_pitch + pitch_noise,
            self.sim_roll + roll_noise,
            self.sim_yaw + yaw_noise
        )
    
    def calibrate(self, duration_seconds: float = 2.0):
        """
        Calibrate IMU by taking static readings
        
        Args:
            duration_seconds: Duration to collect calibration data
        """
        logger.info(f"Calibrating IMU for {duration_seconds} seconds...")
        logger.info("Keep device stationary during calibration")
        
        readings = []
        start_time = time.time()
        
        while time.time() - start_time < duration_seconds:
            data = self.read_sensors()
            readings.append((data.pitch, data.roll, data.yaw))
            time.sleep(1.0 / self.update_rate)
        
        if readings:
            # Average readings to get bias
            avg_pitch = np.mean([r[0] for r in readings])
            avg_roll = np.mean([r[1] for r in readings])
            avg_yaw = np.mean([r[2] for r in readings])
            
            # Store calibration offsets
            self.pitch_offset = avg_pitch
            self.roll_offset = avg_roll
            self.yaw_offset = avg_yaw
            self.is_calibrated = True
            
            # Reset filtered values
            self.filtered_pitch = 0.0
            self.filtered_roll = 0.0
            self.filtered_yaw = 0.0
            
            logger.info(f"Calibration complete: Pitch offset={avg_pitch:.2f}°, "
                       f"Roll offset={avg_roll:.2f}°, Yaw offset={avg_yaw:.2f}°")
        else:
            logger.warning("Calibration failed - no readings")
    
    def get_orientation_matrix(self) -> np.ndarray:
        """
        Get rotation matrix from current orientation
        
        Returns:
            3x3 rotation matrix
        """
        data = self.read_sensors()
        
        # Convert to radians
        pitch_r = math.radians(data.pitch)
        roll_r = math.radians(data.roll)
        yaw_r = math.radians(data.yaw)
        
        # Rotation matrices
        Rx = np.array([
            [1, 0, 0],
            [0, math.cos(pitch_r), -math.sin(pitch_r)],
            [0, math.sin(pitch_r), math.cos(pitch_r)]
        ])
        
        Ry = np.array([
            [math.cos(roll_r), 0, math.sin(roll_r)],
            [0, 1, 0],
            [-math.sin(roll_r), 0, math.cos(roll_r)]
        ])
        
        Rz = np.array([
            [math.cos(yaw_r), -math.sin(yaw_r), 0],
            [math.sin(yaw_r), math.cos(yaw_r), 0],
            [0, 0, 1]
        ])
        
        # Combined rotation: R = Rz * Ry * Rx
        return Rz @ Ry @ Rx
    
    def correct_star_position(self, star_x: float, star_y: float, 
                              focal_length: float) -> Tuple[float, float]:
        """
        Correct star position using IMU orientation
        
        Args:
            star_x, star_y: Star pixel coordinates
            focal_length: Camera focal length in pixels
            
        Returns:
            Corrected (x, y) coordinates
        """
        # Get rotation matrix
        R = self.get_orientation_matrix()
        
        # Convert to 3D vector (assuming camera points at zenith)
        # This is simplified - in production, use proper camera model
        v = np.array([star_x, star_y, focal_length])
        v_normalized = v / np.linalg.norm(v)
        
        # Apply rotation
        v_corrected = R @ v_normalized
        
        # Project back to 2D
        if v_corrected[2] != 0:
            x_corrected = v_corrected[0] * focal_length / v_corrected[2]
            y_corrected = v_corrected[1] * focal_length / v_corrected[2]
        else:
            x_corrected, y_corrected = star_x, star_y
        
        return x_corrected, y_corrected
    
    def reset_simulation(self):
        """Reset simulation to zero"""
        self.sim_pitch = 0.0
        self.sim_roll = 0.0
        self.sim_yaw = 0.0
        self.filtered_pitch = 0.0
        self.filtered_roll = 0.0
        self.filtered_yaw = 0.0
        logger.info("IMU simulation reset")

    def get_orientation(self) -> Tuple[float, float, float]:
        """
        Get current orientation (pitch, roll, yaw)
    
        Returns:
        (pitch, roll, yaw) in degrees
        """
        data = self.read_sensors()
        return data.pitch, data.roll, data.yaw