"""
PiBridge Logger Setup

Simple logging configuration for PiBridge components.
"""

import logging
import sys
from datetime import datetime


def setup_logger(verbose=False, debug=False):
    """Setup logging configuration for PiBridge"""
    
    # Create logger
    logger = logging.getLogger('pibridge')
    logger.setLevel(logging.DEBUG if debug else (logging.INFO if verbose else logging.INFO))
    
    # Create console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG if debug else (logging.INFO if verbose else logging.INFO))
    
    # Create formatter
    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    
    # Add handler to logger
    logger.addHandler(handler)
    
    return logger


def log_operation(logger, operation, status, details=None):
    """Log a standard PiBridge operation"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    if status == 'success':
        logger.info(f"✓ {operation} completed successfully")
    elif status == 'info':
        logger.info(f"ℹ️  {operation}")
    elif status == 'warning':
        logger.warning(f"⚠️  {operation}: {details}")
    elif status == 'error':
        logger.error(f"✗ {operation} failed: {details}")
    
    if details and status in ['success', 'info']:
        logger.info(f"   Details: {details}")