"""
Debug script to test star detection
"""

import cv2
import numpy as np
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from star_detector import StarDetector
import utils

def main():
    print("=" * 60)
    print("TARAPATH - Star Detection Debug")
    print("=" * 60)
    
    # Create test image
    print("\n1. Creating test image...")
    test_image = utils.create_test_image(num_stars=30)
    test_path = "debug_test.jpg"
    cv2.imwrite(test_path, test_image)
    print(f"   Test image saved to {test_path}")
    
    # Load and analyze image
    print("\n2. Analyzing image...")
    img = cv2.imread(test_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    print(f"   Image shape: {gray.shape}")
    print(f"   Min brightness: {np.min(gray)}")
    print(f"   Max brightness: {np.max(gray)}")
    print(f"   Mean brightness: {np.mean(gray):.1f}")
    
    # Try different thresholds
    print("\n3. Testing different thresholds...")
    detector = StarDetector()
    
    thresholds = [20, 30, 40, 50, 60, 70, 80, 90, 100]
    for thresh in thresholds:
        detector.threshold = thresh
        stars = detector.detect(img)
        print(f"   Threshold {thresh}: detected {len(stars)} stars")
    
    # Final detection
    print("\n4. Final detection with best settings...")
    detector.threshold = 30
    stars = detector.detect(img)
    
    print(f"\n   Detected {len(stars)} stars:")
    for i, star in enumerate(stars[:10]):  # Show first 10
        print(f"     Star {i+1}: pos=({star.x:.1f}, {star.y:.1f}), "
              f"brightness={star.peak_intensity:.0f}")
    
    # Visualize
    print("\n5. Creating visualization...")
    for star in stars:
        cv2.circle(img, (int(star.x), int(star.y)), 5, (0, 255, 0), 2)
        cv2.putText(img, f"{star.peak_intensity:.0f}", 
                   (int(star.x)+10, int(star.y)),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
    
    vis_path = "debug_visualization.jpg"
    cv2.imwrite(vis_path, img)
    print(f"   Visualization saved to {vis_path}")
    
    print("\n" + "=" * 60)
    print("Debug complete!")
    print("=" * 60)

if __name__ == "__main__":
    main()