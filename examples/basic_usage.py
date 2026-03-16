#!/usr/bin/env python3
"""
TARAPATH - Basic Usage Example
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
 
from tarapath_core import TARAPATH
import utils
from datetime import datetime
import cv2

def main():
    """Basic usage example"""
    print("=" * 60)
    print("TARAPATH - Basic Usage Example")
    print("=" * 60)
    
    # Initialize TARAPATH
    print("\n1. Initializing TARAPATH...")
    nav = TARAPATH()
    
    # Create a test image
    print("\n2. Creating test star field...")
    test_image = utils.create_test_image(num_stars=30)
    test_path = "../test_stars.jpg"
    cv2.imwrite(test_path, test_image)
    print(f"   Test image saved to {test_path}")
    
    # Process the image
    print("\n3. Processing image...")
    timestamp = datetime.now()
    position = nav.process_image(test_path, timestamp)
    
    if position:
        print("\n" + "=" * 50)
        print("NAVIGATION RESULTS")
        print("=" * 50)
        print(f"Latitude:  {position.latitude:.6f}°")
        print(f"Longitude: {position.longitude:.6f}°")
        print(f"Confidence: {position.confidence:.1%}")
        print(f"Error radius: {position.error_radius:.1f} meters")
        print(f"Stars used: {position.num_stars_used}")
        
        # Visualize
        print("\n4. Generating visualization...")
        nav.visualize_results(test_path, "../result.jpg")
        print("   Visualization saved to ../result.jpg")
    else:
        print("\n❌ Failed to determine position")
    
    print("\n" + "=" * 60)
    print("Example completed!")
    print("=" * 60)

if __name__ == "__main__":
    main()

