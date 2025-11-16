"""
Network scanning API endpoints for PiBridge Web UI

Provides endpoints to scan for available WiFi networks and interact with the WiFiScanner class.
"""

import sys
import os
from flask import Blueprint, jsonify, request
from datetime import datetime

# Add parent directory to path to import pibridge modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import PiBridge modules (modules are now at root level)
try:
    from scanner import WiFiScanner, WiFiNetwork
    from config_manager import ConfigManager
    from logger import setup_logger
    from exceptions import NoInterfaceException
except ImportError as e:
    print(f"Warning: Could not import PiBridge modules: {e}")
    # Mock classes for development
    class WiFiScanner:
        def scan(self): return []
    
    class ConfigManager:
        def list_networks(self): return []
    
    def setup_logger(*args, **kwargs): 
        return type('Logger', (), {'info': print, 'error': print, 'warning': print})()

bp = Blueprint('networks', __name__)
# Initialize logger (with fallback if import fails)
try:
    from logger import setup_logger
    logger = setup_logger(verbose=False, debug=False)
except ImportError:
    import logging
    logger = logging.getLogger('pibridge-web-networks')
    logger.addHandler(logging.StreamHandler())
    logger.setLevel(logging.INFO)


@bp.route('/networks', methods=['GET'])
def get_networks():
    """
    Scan for available WiFi networks
    
    Returns:
        JSON response with list of networks including:
        - ssid: Network name
        - signal: Signal strength in dBm
        - signal_quality: Quality description (Excellent/Good/Fair/Weak)
        - security: Security type (WPA2/WPA3/WEP/Open)
        - frequency: Frequency band (2.4 GHz/5 GHz)
        - in_use: Whether currently connected to this network
        - saved: Whether this network is in saved networks list
    """
    try:
        logger.info("API: Scanning for networks...")
        
        # Scan for available networks
        scanner = WiFiScanner()
        networks = scanner.scan()
        
        # Get saved networks
        config = ConfigManager()
        saved_networks = config.list_networks()
        saved_ssids = {net['ssid'] for net in saved_networks}
        
        # Convert to serializable format
        network_list = []
        for net in networks:
            network_data = {
                'ssid': net.ssid,
                'signal': net.signal,
                'signal_quality': net.signal_quality,
                'security': net.security,
                'frequency': net.frequency,
                'in_use': net.in_use,
                'saved': net.ssid in saved_ssids
            }
            network_list.append(network_data)
        
        logger.info(f"API: Found {len(network_list)} networks")
        
        return jsonify({
            'success': True,
            'networks': network_list,
            'count': len(network_list),
            'timestamp': datetime.now().isoformat()
        })
        
    except NoInterfaceException as e:
        logger.error(f"API: No wireless interface found: {e}")
        return jsonify({
            'success': False,
            'error': 'No wireless interface found. Please check your WiFi hardware.'
        }), 400
        
    except Exception as e:
        logger.error(f"API: Error scanning networks: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to scan networks: {str(e)}'
        }), 500


@bp.route('/networks/saved', methods=['GET'])
def get_saved_networks():
    """
    Get list of saved network configurations
    
    Returns:
        JSON response with list of saved networks including:
        - ssid: Network name
        - added_date: When the network was saved
        - last_connected: When it was last successfully connected
        - security: Security type
    """
    try:
        logger.info("API: Getting saved networks...")
        
        config = ConfigManager()
        saved_networks = config.list_networks()
        
        # Convert to serializable format
        network_list = []
        for net in saved_networks:
            network_data = {
                'ssid': net['ssid'],
                'added_date': net.get('added_date', 'Unknown'),
                'last_connected': net.get('last_connected', 'Never'),
                'security': 'WPA2'  # Default for now, could be stored in config
            }
            network_list.append(network_data)
        
        logger.info(f"API: Found {len(network_list)} saved networks")
        
        return jsonify({
            'success': True,
            'networks': network_list,
            'count': len(network_list)
        })
        
    except Exception as e:
        logger.error(f"API: Error getting saved networks: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to get saved networks: {str(e)}'
        }), 500


@bp.route('/networks/forget/<ssid>', methods=['POST'])
def forget_network(ssid):
    """
    Remove a saved network
    
    Args:
        ssid: The network SSID to forget
        
    Returns:
        JSON response indicating success or failure
    """
    try:
        logger.info(f"API: Forgetting network '{ssid}'...")
        
        config = ConfigManager()
        
        # Check if network exists
        saved_networks = config.list_networks()
        if not any(net['ssid'] == ssid for net in saved_networks):
            return jsonify({
                'success': False,
                'error': f"Network '{ssid}' not found in saved networks"
            }), 404
        
        # Remove the network
        if config.remove_network(ssid):
            logger.info(f"API: Successfully removed '{ssid}'")
            return jsonify({
                'success': True,
                'message': f"Successfully removed '{ssid}'"
            })
        else:
            logger.error(f"API: Failed to remove '{ssid}'")
            return jsonify({
                'success': False,
                'error': f"Failed to remove '{ssid}'"
            }), 500
            
    except Exception as e:
        logger.error(f"API: Error forgetting network '{ssid}': {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to forget network: {str(e)}'
        }), 500