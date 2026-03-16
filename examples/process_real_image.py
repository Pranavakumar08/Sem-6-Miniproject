#!/usr/bin/env python3
"""
TARAPATH - Process Real Image Example
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
 
from tarapath_core import TARAPATH
from datetime import datetime
import argparse

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Process a real night sky image')
    parser.add_argument('image', help='Path to night sky image')
    parser.add_argument('--timestamp', help='Image capture time (YYYY-MM-DD HH:MM:SS)')
    parser.add_argument('--output', '-o', default='../result.jpg', help='Output path')
    return parser.parse_args()

def parse_timestamp(timestamp_str):
    """Parse timestamp string"""
    if timestamp_str is None:
        return None
    
    formats = [
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d %H:%M',
        '%Y/%m/%d %H:%M:%S',
        '%Y/%m/%d %H:%M',
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(timestamp_str, fmt)
        except ValueError:
            continue
    
    raise ValueError(f"Unable to parse timestamp: {timestamp_str}")

def main():
    """Main function"""
    args = parse_args()
    
    print("=" * 60)
    print("TARAPATH - Real Image Processing")
    print("=" * 60)
    
    # Check if image exists
    if not os.path.exists(args.image):
        print(f"Error: Image not found: {args.image}")
        return 1
    
    # Parse timestamp
    timestamp = parse_timestamp(args.timestamp)
    if args.timestamp and timestamp is None:
        return 1
    
    # Initialize TARAPATH
    print("\n1. Initializing TARAPATH...")
    nav = TARAPATH()
    
    # Process image
    print(f"\n2. Processing image: {args.image}")
    if timestamp:
        print(f"   Using timestamp: {timestamp}")
    
    position = nav.process_image(args.image, timestamp)
    
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
        print(f"\n3. Generating visualization: {args.output}")
        nav.visualize_results(args.image, args.output)
    else:
        print("\n❌ Failed to determine position")
        return 1
    
    print("\n" + "=" * 60)
    print("Processing completed!")
    print("=" * 60)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

