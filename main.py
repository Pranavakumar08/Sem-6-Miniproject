#!/usr/bin/env python3
"""
TARAPATH - Offline Celestial Navigation System
Main entry point for the application
"""

import argparse
import sys
import os
from datetime import datetime
import logging

# Fix the import - use relative import or ensure tarapath_core is in path
try:
    from tarapath_core import TARAPATH
except ImportError:
    # If running directly, add current directory to path
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from tarapath_core import TARAPATH

from config import config
import utils

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='TARAPATH - Offline Celestial Navigation System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s image.jpg
  %(prog)s image.jpg --timestamp "2024-03-15 22:30:00"
  %(prog)s image.jpg --output result.jpg --save
  %(prog)s --test
        """
    )
    
    parser.add_argument('image', nargs='?', help='Path to night sky image')
    parser.add_argument('--timestamp', help='Image capture time (YYYY-MM-DD HH:MM:SS)')
    parser.add_argument('--output', '-o', help='Output visualization path')
    parser.add_argument('--save', '-s', action='store_true', help='Save results to file')
    parser.add_argument('--test', action='store_true', help='Run with test image')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('--no-imu', action='store_true', help='Disable IMU correction')
    
    return parser.parse_args()

def setup_environment(args):
    """Setup environment and logging"""
    # Determine log level as string
    log_level_str = 'DEBUG' if args.debug else 'INFO'
    
    # Setup logging with string level
    utils.setup_logging(log_level_str, 'tarapath.log')
    
    # Create necessary directories
    os.makedirs(config.catalog.catalog_path, exist_ok=True)
    os.makedirs(config.results_path, exist_ok=True)
    
    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info("TARAPATH - Offline Celestial Navigation System")
    logger.info("=" * 60)
    
    return logger

def parse_timestamp(timestamp_str: str) -> datetime:
    """Parse timestamp string to datetime"""
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

def run_with_test_image(nav, args) -> bool:
    """Run system with test image"""
    logger = logging.getLogger(__name__)
    
    try:
        import cv2
    except ImportError:
        logger.error("OpenCV (cv2) is required. Please install: pip install opencv-python")
        return False
    
    # Create test image
    logger.info("Creating test star field...")
    test_image = utils.create_test_image(num_stars=30)
    test_path = "test_stars.jpg"
    cv2.imwrite(test_path, test_image)
    logger.info(f"Test image saved to {test_path}")
    
    # Process test image
    logger.info("Processing test image...")
    timestamp = datetime.now()
    position = nav.process_image(test_path, timestamp, use_imu=not args.no_imu)
    
    if position:
        logger.info("\n" + "=" * 50)
        logger.info("NAVIGATION RESULTS")
        logger.info("=" * 50)
        logger.info(f"Latitude:  {position.latitude:.6f}°")
        logger.info(f"Longitude: {position.longitude:.6f}°")
        logger.info(f"Confidence: {position.confidence:.1%}")
        logger.info(f"Error radius: {position.error_radius:.1f} meters")
        logger.info(f"Stars used: {position.num_stars_used}")
        
        # Save results
        if args.save:
            results = {
                'timestamp': timestamp.isoformat(),
                'position': {
                    'latitude': position.latitude,
                    'longitude': position.longitude,
                    'confidence': position.confidence,
                    'error_radius': position.error_radius
                },
                'num_stars': position.num_stars_used,
                'residuals': position.residuals
            }
            utils.save_results(results, f"{config.results_path}/test_results.json")
        
        # Visualize
        output = args.output or "test_result.jpg"
        nav.visualize_results(test_path, output)
        logger.info(f"Visualization saved to {output}")
        
        return True
    else:
        logger.error("Failed to determine position")
        return False

def run_with_real_image(nav, args) -> bool:
    """Run system with real image"""
    logger = logging.getLogger(__name__)
    
    # Parse timestamp
    timestamp = None
    if args.timestamp:
        try:
            timestamp = parse_timestamp(args.timestamp)
            logger.info(f"Using provided timestamp: {timestamp}")
        except ValueError as e:
            logger.error(e)
            return False
    
    # Process image
    logger.info(f"Processing image: {args.image}")
    position = nav.process_image(args.image, timestamp, use_imu=not args.no_imu)
    
    if position:
        logger.info("\n" + "=" * 50)
        logger.info("NAVIGATION RESULTS")
        logger.info("=" * 50)
        logger.info(f"Latitude:  {position.latitude:.6f}°")
        logger.info(f"Longitude: {position.longitude:.6f}°")
        logger.info(f"Confidence: {position.confidence:.1%}")
        logger.info(f"Error radius: {position.error_radius:.1f} meters")
        logger.info(f"Stars used: {position.num_stars_used}")
        
        # Save results
        if args.save:
            results = {
                'image': args.image,
                'timestamp': (timestamp or datetime.now()).isoformat(),
                'position': {
                    'latitude': position.latitude,
                    'longitude': position.longitude,
                    'confidence': position.confidence,
                    'error_radius': position.error_radius
                },
                'num_stars': position.num_stars_used,
                'residuals': position.residuals
            }
            results_filename = f"{config.results_path}/result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            utils.save_results(results, results_filename)
        
        # Visualize
        output = args.output or f"{config.results_path}/visualization.jpg"
        nav.visualize_results(args.image, output)
        logger.info(f"Visualization saved to {output}")
        
        return True
    else:
        logger.error("Failed to determine position")
        return False

def main():
    """Main entry point"""
    args = parse_arguments()
    logger = setup_environment(args)
    
    # Check if we have an image or test mode
    if not args.image and not args.test:
        logger.error("Please provide an image path or use --test")
        print("\nError: No image specified. Use --help for usage information.")
        sys.exit(1)
    
    try:
        # Import cv2 here to avoid import errors if not needed
        import cv2
        
        # Initialize TARAPATH
        logger.info("Initializing TARAPATH...")
        nav = TARAPATH(test_mode=True)
        
        # Run in appropriate mode
        if args.test:
            success = run_with_test_image(nav, args)
        else:
            success = run_with_real_image(nav, args)
        
        if success:
            logger.info("\nTARAPATH completed successfully!")
            sys.exit(0)
        else:
            logger.error("\nTARAPATH failed to determine position")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("\nInterrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()