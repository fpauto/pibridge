"""
Connection management API endpoints for PiBridge Web UI

Provides endpoints to connect and disconnect from WiFi networks using the WiFiConnector class.
"""

import sys
import os
from flask import Blueprint, jsonify, request
from datetime import datetime

# Add parent directory to path to import pibridge modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import PiBridge modules (modules are now at root level)
try:
    from connector import WiFiConnector
    from config_manager import ConfigManager
    from rfkill_checker import check_rfkill
    from logger import setup_logger
    from exceptions import (
        ConnectionFailedException,
        NoSavedNetworksException,
        RfkillBlockedException
    )
except ImportError as e:
    print(f"Warning: Could not import PiBridge modules: {e}")
    # Mock classes for development
    class WiFiConnector:
        def connect(self, ssid, password): return True
        def disconnect(self): return True
        def auto_connect(self, networks): return True
        def get_current_connection(self): return None
    
    class ConfigManager:
        def list_networks(self): return []
        def save_network(self, ssid, password): pass
        def update_last_connected(self, ssid): pass
    
    def check_rfkill(): pass
    
    def setup_logger(*args, **kwargs): 
        return type('Logger', (), {'info': print, 'error': print, 'warning': print})()

bp = Blueprint('connection', __name__)
logger = setup_logger(verbose=False, debug=False)


@bp.route('/connect', methods=['POST'])
def connect_network():
    """
    Connect to a WiFi network
    
    JSON body:
        - ssid: Network SSID (required)
        - password: Network password (required)
        
    Returns:
        JSON response indicating success or failure
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'No JSON data provided'
            }), 400
        
        ssid = data.get('ssid', '').strip()
        password = data.get('password', '').strip()
        
        if not ssid:
            return jsonify({
                'success': False,
                'error': 'Network SSID is required'
            }), 400
        
        if not password:
            return jsonify({
                'success': False,
                'error': 'Network password is required'
            }), 400
        
        logger.info(f"API: Connecting to network '{ssid}'...")
        
        # Check rfkill status
        try:
            check_rfkill()
        except RfkillBlockedException as e:
            return jsonify({
                'success': False,
                'error': f'Wireless is blocked: {str(e)}'
            }), 400
        
        # Connect to network
        connector = WiFiConnector()
        success = connector.connect(ssid, password)
        
        if success:
            # Save credentials to config
            config = ConfigManager()
            config.save_network(ssid, password)
            config.update_last_connected(ssid)
            
            logger.info(f"API: Successfully connected to '{ssid}'")
            return jsonify({
                'success': True,
                'message': f"Successfully connected to '{ssid}'",
                'network': ssid
            })
        else:
            logger.error(f"API: Failed to connect to '{ssid}'")
            return jsonify({
                'success': False,
                'error': f'Failed to connect to {ssid}. Please check the password.'
            }), 400
            
    except ConnectionFailedException as e:
        logger.error(f"API: Connection failed: {e}")
        return jsonify({
            'success': False,
            'error': f'Connection failed: {str(e)}'
        }), 400
        
    except Exception as e:
        logger.error(f"API: Error connecting to network: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to connect: {str(e)}'
        }), 500


@bp.route('/auto-connect', methods=['POST'])
def auto_connect():
    """
    Auto-connect to the strongest available saved network
    
    Returns:
        JSON response indicating success or failure
    """
    try:
        logger.info("API: Attempting auto-connect to strongest saved network...")
        
        # Check rfkill status
        try:
            check_rfkill()
        except RfkillBlockedException as e:
            return jsonify({
                'success': False,
                'error': f'Wireless is blocked: {str(e)}'
            }), 400
        
        # Get saved networks
        config = ConfigManager()
        saved_networks = config.list_networks()
        
        if not saved_networks:
            return jsonify({
                'success': False,
                'error': 'No saved networks found'
            }), 400
        
        # Auto-connect
        connector = WiFiConnector()
        success = connector.auto_connect(saved_networks)
        
        if success:
            # Find which network we connected to
            current = connector.get_current_connection()
            if current:
                config.update_last_connected(current)
                logger.info(f"API: Successfully auto-connected to '{current}'")
                return jsonify({
                    'success': True,
                    'message': f"Successfully connected to '{current}'",
                    'network': current
                })
            else:
                logger.info("API: Auto-connected successfully")
                return jsonify({
                    'success': True,
                    'message': 'Successfully connected to strongest saved network'
                })
        else:
            logger.error("API: Auto-connect failed")
            return jsonify({
                'success': False,
                'error': 'No saved networks are available or connection failed'
            }), 400
            
    except NoSavedNetworksException as e:
        logger.error(f"API: No saved networks: {e}")
        return jsonify({
            'success': False,
            'error': 'No saved networks found'
        }), 400
        
    except Exception as e:
        logger.error(f"API: Error during auto-connect: {e}")
        return jsonify({
            'success': False,
            'error': f'Auto-connect failed: {str(e)}'
        }), 500


@bp.route('/disconnect', methods=['POST'])
def disconnect():
    """
    Disconnect from current network
    
    Returns:
        JSON response indicating success or failure
    """
    try:
        logger.info("API: Disconnecting from current network...")
        
        connector = WiFiConnector()
        
        # Check current connection
        current = connector.get_current_connection()
        if not current:
            logger.info("API: No active connection to disconnect")
            return jsonify({
                'success': True,
                'message': 'Not currently connected to any network'
            })
        
        # Disconnect
        success = connector.disconnect()
        
        if success:
            logger.info(f"API: Successfully disconnected from '{current}'")
            
            # Check if interface is available for hotspot
            is_available, status_msg = connector.is_interface_available_for_hotspot()
            
            return jsonify({
                'success': True,
                'message': f"Successfully disconnected from '{current}'",
                'interface_available': is_available,
                'interface_status': status_msg
            })
        else:
            logger.error(f"API: Failed to disconnect from '{current}'")
            return jsonify({
                'success': False,
                'error': f'Failed to disconnect from {current}'
            }), 500
            
    except Exception as e:
        logger.error(f"API: Error during disconnection: {e}")
        return jsonify({
            'success': False,
            'error': f'Disconnection failed: {str(e)}'
        }), 500


@bp.route('/current-connection', methods=['GET'])
def get_current_connection():
    """
    Get current connection information
    
    Returns:
        JSON response with current connection details
    """
    try:
        logger.info("API: Getting current connection...")
        
        connector = WiFiConnector()
        current = connector.get_current_connection()
        
        if current:
            # Get signal strength if available
            signal_info = None
            try:
                from scanner import WiFiScanner
                scanner = WiFiScanner()
                networks = scanner.scan()
                for net in networks:
                    if net.ssid == current and net.in_use:
                        signal_info = {
                            'signal': net.signal,
                            'signal_quality': net.signal_quality
                        }
                        break
            except:
                pass  # Signal info is optional
            
            response = {
                'success': True,
                'connected': True,
                'network': current,
                'timestamp': datetime.now().isoformat()
            }
            
            if signal_info:
                response.update(signal_info)
            
            return jsonify(response)
        else:
            return jsonify({
                'success': True,
                'connected': False,
                'network': None,
                'message': 'Not currently connected'
            })
            
    except Exception as e:
        logger.error(f"API: Error getting current connection: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to get current connection: {str(e)}'
        }), 500