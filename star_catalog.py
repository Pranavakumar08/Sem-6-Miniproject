"""
TARAPATH - Star Catalog Management
Pure Python implementation, no compilation required
"""

import numpy as np
import pandas as pd
import requests
import gzip
import io
import os
import pickle
from typing import List, Dict, Optional, Tuple
import logging
from datetime import datetime
import math

from config import config
from utils import angular_distance

logger = logging.getLogger(__name__)

class StarCatalog:
    """
    Pure Python star catalog using HYG database
    No compilation, no special dependencies
    """
    
    def __init__(self, catalog_path: str = None):
        """
        Initialize star catalog
        
        Args:
            catalog_path: Path to store/load catalog
        """
        self.catalog_path = catalog_path or config.catalog.catalog_path
        self.max_magnitude = config.catalog.max_magnitude
        self.stars_df = None
        self.cache = {}
        self._initialize_catalog()
    
    def _download_hyg_catalog(self) -> pd.DataFrame:
        """Download the HYG database (standard astronomy catalog)"""
        logger.info("Downloading HYG star catalog...")
        
        # Try multiple URLs for the HYG database
        urls = [
            "https://raw.githubusercontent.com/astronexus/HYG-Database/main/hygdata_v3.csv",
            "https://github.com/astronexus/HYG-Database/raw/main/hygdata_v3.csv",
            "https://astronexus.com/files/downloads/hygdata_v3.csv"
        ]
        
        for url in urls:
            try:
                logger.info(f"Trying URL: {url}")
                response = requests.get(url, timeout=30)
                response.raise_for_status()
                
                # Read into pandas
                from io import StringIO
                df = pd.read_csv(StringIO(response.text))
                logger.info(f"Downloaded {len(df)} stars from {url}")
                return df
                
            except Exception as e:
                logger.warning(f"Download from {url} failed: {e}")
                continue
        
        logger.warning("All download attempts failed. Using fallback catalog.")
        return self._create_fallback_catalog()
    
    def _create_fallback_catalog(self) -> pd.DataFrame:
        """Create a fallback catalog with the 100 brightest stars"""
        # Data for 100 brightest stars (simplified - first 20 shown here)
        # In production, this would contain all 100 stars
        bright_stars = {
            'hip': list(range(1, 101)),
            'ra': [101.287, 95.987, 219.900, 213.915, 279.234, 79.172, 78.634, 114.825, 
                   24.428, 88.793, 210.956, 297.695, 186.650, 68.980, 201.298, 247.352,
                   116.329, 344.413, 310.358, 152.093] + [0] * 80,
            'dec': [-16.716, -52.696, -60.833, 19.182, 38.784, 45.998, -8.202, 5.225,
                    -57.236, 7.407, -60.373, 8.868, -63.099, 16.509, -11.161, -26.432,
                    28.026, -29.622, 45.280, 11.967] + [0] * 80,
            'mag': [-1.46, -0.72, -0.27, -0.05, 0.03, 0.08, 0.12, 0.34, 0.46, 0.50,
                    0.61, 0.76, 0.77, 0.87, 0.98, 1.06, 1.16, 1.17, 1.25, 1.35] + [10] * 80,
            'name': ['Sirius', 'Canopus', 'Alpha Centauri', 'Arcturus', 'Vega',
                    'Capella', 'Rigel', 'Procyon', 'Achernar', 'Betelgeuse',
                    'Hadar', 'Altair', 'Acrux', 'Aldebaran', 'Spica',
                    'Antares', 'Pollux', 'Fomalhaut', 'Deneb', 'Regulus'] + ['Unknown'] * 80
        }
        
        # Truncate to actual length
        for key in bright_stars:
            bright_stars[key] = bright_stars[key][:100]
        
        df = pd.DataFrame(bright_stars)
        return df
    
    def _initialize_catalog(self):
        """Initialize the star catalog"""
        os.makedirs(self.catalog_path, exist_ok=True)
        csv_path = os.path.join(self.catalog_path, "hyg_stars.csv")
        pkl_path = os.path.join(self.catalog_path, "hyg_stars.pkl")
        
        # Try to load pickled version first (faster)
        if os.path.exists(pkl_path):
            try:
                logger.info(f"Loading pickled catalog from {pkl_path}")
                with open(pkl_path, 'rb') as f:
                    self.stars_df = pickle.load(f)
                logger.info(f"Loaded {len(self.stars_df)} stars")
                return
            except Exception as e:
                logger.warning(f"Failed to load pickled catalog: {e}")
        
        # Try to load CSV
        if os.path.exists(csv_path):
            logger.info(f"Loading existing catalog from {csv_path}")
            self.stars_df = pd.read_csv(csv_path)
        else:
            # Download and save
            self.stars_df = self._download_hyg_catalog()
            self.stars_df.to_csv(csv_path, index=False)
            logger.info(f"Saved catalog to {csv_path}")
        
        # Filter for bright stars
        if 'mag' in self.stars_df.columns:
            self.stars_df = self.stars_df[self.stars_df['mag'] <= self.max_magnitude].copy()
            logger.info(f"Filtered to {len(self.stars_df)} bright stars (mag <= {self.max_magnitude})")
        
        # Save pickled version for faster loading next time
        try:
            with open(pkl_path, 'wb') as f:
                pickle.dump(self.stars_df, f)
            logger.info(f"Saved pickled catalog to {pkl_path}")
        except Exception as e:
            logger.warning(f"Failed to save pickled catalog: {e}")
    
    def query_cone(self, center_ra: float, center_dec: float, 
                   radius_deg: float, max_stars: int = 50) -> List[Dict]:
        """
        Find stars within a cone on the celestial sphere
        
        Args:
            center_ra: Right Ascension of center (degrees)
            center_dec: Declination of center (degrees)
            radius_deg: Search radius (degrees)
            max_stars: Maximum number of stars to return
            
        Returns:
            List of stars with RA, Dec, magnitude
        """
        if self.stars_df is None or len(self.stars_df) == 0:
            return []
        
        # Check cache
        cache_key = (round(center_ra, 1), round(center_dec, 1), round(radius_deg, 1))
        if cache_key in self.cache:
            return self.cache[cache_key][:max_stars]
        
        # Calculate distances for all stars
        stars_in_cone = []
        
        for _, star in self.stars_df.iterrows():
            dist = angular_distance(
                center_ra, center_dec,
                star['ra'], star['dec']
            )
            if dist <= radius_deg:
                stars_in_cone.append({
                    'ra': float(star['ra']),
                    'dec': float(star['dec']),
                    'magnitude': float(star['mag']),
                    'name': star.get('name', f"HIP{star.get('hip', 'Unknown')}"),
                    'hip': star.get('hip', None),
                    'distance': dist
                })
        
        # Sort by brightness (magnitude) and then distance
        stars_in_cone.sort(key=lambda x: (x['magnitude'], x['distance']))
        
        # Cache result
        if len(self.cache) < config.catalog.cache_size:
            self.cache[cache_key] = stars_in_cone
        
        return stars_in_cone[:max_stars]
    
    def get_star_by_name(self, name: str) -> Optional[Dict]:
        """Get star by name"""
        if self.stars_df is None:
            return None
        
        star = self.stars_df[self.stars_df['name'] == name]
        if len(star) == 0:
            return None
        
        return {
            'ra': float(star.iloc[0]['ra']),
            'dec': float(star.iloc[0]['dec']),
            'magnitude': float(star.iloc[0]['mag']),
            'name': name
        }
    
    def get_star_by_hip(self, hip: int) -> Optional[Dict]:
        """Get star by Hipparcos catalog number"""
        if self.stars_df is None:
            return None
        
        star = self.stars_df[self.stars_df['hip'] == hip]
        if len(star) == 0:
            return None
        
        return {
            'ra': float(star.iloc[0]['ra']),
            'dec': float(star.iloc[0]['dec']),
            'magnitude': float(star.iloc[0]['mag']),
            'name': star.iloc[0].get('name', f"HIP{hip}"),
            'hip': hip
        }
    
    def get_brightest_stars(self, n: int = 10) -> List[Dict]:
        """Get the n brightest stars"""
        if self.stars_df is None:
            return []
        
        brightest = self.stars_df.nsmallest(n, 'mag')
        return [{
            'ra': float(row['ra']),
            'dec': float(row['dec']),
            'magnitude': float(row['mag']),
            'name': row.get('name', f"HIP{row.get('hip', 'Unknown')}")
        } for _, row in brightest.iterrows()]
    
    def get_constellation_stars(self, constellation: str) -> List[Dict]:
        """Get stars in a constellation (if data available)"""
        if self.stars_df is None or 'con' not in self.stars_df.columns:
            return []
        
        stars = self.stars_df[self.stars_df['con'] == constellation]
        return [{
            'ra': float(row['ra']),
            'dec': float(row['dec']),
            'magnitude': float(row['mag']),
            'name': row.get('name', f"HIP{row.get('hip', 'Unknown')}")
        } for _, row in stars.iterrows()]
    
    def clear_cache(self):
        """Clear the query cache"""
        self.cache.clear()
        logger.info("Cache cleared")

