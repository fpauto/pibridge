#!/usr/bin/env python3
"""
Test script to directly test HotspotManager without web API
"""

import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from hotspot import HotspotManager
    from logger import setup_logger
    
    logger = setup_logger(verbose=True, debug=True)
    logger.info("Testing HotspotManager directly...")
    
    # Create hotspot manager
    hotspot = HotspotManager()
    logger.info(f"Hotspot manager created. Interface: {hotspot.interface}")
    
    # Test starting the hotspot
    logger.info("Attempting to start hotspot...")
    success = hotspot.start_hotspot()
    
    if success:
        logger.info("✓ Hotspot started successfully!")
        status = hotspot.get_status()
        logger.info(f"  Status: {'Active' if status.active else 'Inactive'}")
        logger.info(f"  SSID: {status.ssid}")
        logger.info(f"  Interface: {status.interface}")
        logger.info(f"  IP: {status.ip_address}")
        logger.info(f"  Clients: {status.clients}")
    else:
        logger.error("✗ Failed to start hotspot")
        
except Exception as e:
    logger.error(f"Error testing hotspot: {e}")
    import traceback
    traceback.print_exc()