#!/usr/bin/env python3
"""
PiBridge Module Entry Point

This module handles the command-line execution when using python3 -m pibridge
"""

import sys
import argparse
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from pibridge.cli import main


def module_main():
    """Main entry point for python3 -m pibridge execution"""
    return main()


if __name__ == '__main__':
    sys.exit(module_main())