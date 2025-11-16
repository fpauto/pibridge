"""
Status information API endpoints for PiBridge Web UI

Provides endpoints to get overall system status and information.
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
    from scanner import WiFiScanner
    from config_manager import ConfigManager
    from hotspot import HotspotManager
    from logger import setup_logger
except ImportError as e:
    print(f"Warning: Could not import PiBridge modules: {e}")
    # Mock classes for development
    class WiFiConnector:
        def get_current_connection(self): return None
        def is_interface_available_for_hotspot(self): return True, "Interface available"
    
    class WiFiScanner:
        def scan(self): return []
    
    class ConfigManager:
        def list_networks(self): return []
    
    class HotspotManager:
        def get_status(self):
            class MockStatus:
                active = False
                ssid = "pibridge"
                interface = "wlan0"
                ip_address = "192.168.4.1"
                clients = 0
            return MockStatus()
    
    def setup_logger(*args, **kwargs): 
        return type('Logger', (), {'info': print, 'error': print, 'warning': print})()

bp = Blueprint('status', __name__)
logger = setup_logger(verbose=False, debug=False)


@bp.route('/status', methods=['GET'])
def get_overall_status():
    """
    Get overall system status including connection, hotspot, and service information
    
    Returns:
        JSON response with comprehensive system status
    """
    try:
        logger.info("API: Getting overall system status...")
        
        # Get current connection status
        connector = WiFiConnector()
        current_network = connector.get_current_connection()
        
        # Get signal strength if connected
        signal_info = None
        if current_network:
            try:
                scanner = WiFiScanner()
                networks = scanner.scan()
                for net in networks:
                    if net.ssid == current_network and net.in_use:
                        signal_info = {
                            'signal': net.signal,
                            'signal_quality': net.signal_quality
                        }
                        break
            except Exception:
                pass  # Signal info is optional
        
        # Get saved networks count
        config = ConfigManager()
        saved_networks = config.list_networks()
        saved_count = len(saved_networks)
        
        # Get hotspot status
        hotspot = HotspotManager()
        hotspot_status = hotspot.get_status()
        
        # Check interface availability
        interface_available, interface_status = connector.is_interface_available_for_hotspot()
        
        # Build response
        status_response = {
            'success': True,
            'timestamp': datetime.now().isoformat(),
            'connection': {
                'connected': current_network is not None,
                'network': current_network,
                'interface': connector.interface,
                'interface_available': interface_available,
                'interface_status': interface_status
            },
            'signal': signal_info,
            'hotspot': {
                'active': hotspot_status.active,
                'ssid': hotspot_status.ssid if hotspot_status.active else None,
                'interface': hotspot_status.interface,
                'ip_address': hotspot_status.ip_address if hotspot_status.active else None,
                'clients': hotspot_status.clients
            },
            'networks': {
                'saved_count': saved_count,
                'total_available': 0  # Will be filled by scanning if needed
            },
            'services': {
                'web_ui': {
                    'available': True,
                    'enabled': False,  # Would need to check systemd service
                    'active': False     # Would need to check systemd service
                },
                'auto_recovery': {
                    'available': True,
                    'enabled': False,  # Would need to check systemd service
                    'active': False    # Would need to check systemd service
                },
                'hotspot_service': {
                    'available': True,
                    'enabled': False,  # Would need to check systemd service
                    'active': False    # Would need to check systemd service
                }
            }
        }
        
        logger.info(f"API: Overall status - Connected: {current_network is not None}, Hotspot: {hotspot_status.active}")
        return jsonify(status_response)
        
    except Exception as e:
        logger.error(f"API: Error getting overall status: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to get system status: {str(e)}'
        }), 500


@bp.route('/status/dashboard', methods=['GET'])
def get_dashboard_status():
    """
    Get simplified dashboard status suitable for real-time updates
    
    Returns:
        JSON response with key information for dashboard display
    """
    try:
        logger.info("API: Getting dashboard status...")
        
        # Initialize with default values
        current_network = None
        signal_strength = None
        signal_quality = None
        current_ip = None
        hotspot_status = None
        interface = "wlan0"  # Default interface
        
        try:
            # Get current connection
            connector = WiFiConnector()
            current_network = connector.get_current_connection()
            interface = getattr(connector, 'interface', 'wlan0')
        except Exception as e:
            logger.warning(f"Could not get connection status: {e}")
        
        if current_network:
            try:
                scanner = WiFiScanner()
                networks = scanner.scan()
                
                # Find the connected network with signal info
                for net in networks:
                    if net.in_use or (net.ssid == current_network and net.signal is not None):
                        signal_strength = net.signal
                        signal_quality = net.signal_quality
                        break
                
                # If not found in scan results, try to get IP from connector
                if signal_strength is None:
                    try:
                        import subprocess
                        result = subprocess.run(['ip', 'addr', 'show', interface],
                                              capture_output=True, text=True)
                        if result.returncode == 0:
                            for line in result.stdout.split('\n'):
                                if 'inet ' in line and 'scope global' in line:
                                    parts = line.strip().split()
                                    ip_idx = parts.index('inet')
                                    if ip_idx + 1 < len(parts):
                                        current_ip = parts[ip_idx + 1].split('/')[0]
                                        break
                    except Exception:
                        pass
                        
            except Exception as e:
                logger.warning(f"Could not get signal strength: {e}")
        
        try:
            # Get hotspot status
            hotspot = HotspotManager()
            hotspot_status = hotspot.get_status()
        except Exception as e:
            logger.warning(f"Could not get hotspot status: {e}")
            # Create mock hotspot status
            class MockStatus:
                active = False
                ssid = "pibridge"
                ip_address = "192.168.4.1"
                clients = 0
            hotspot_status = MockStatus()
        
        response = {
            'success': True,
            'timestamp': datetime.now().isoformat(),
            'dashboard': {
                'connection_status': 'Connected' if current_network else 'Disconnected',
                'current_network': current_network,
                'signal_strength': signal_strength,
                'signal_quality': signal_quality,
                'current_ip': current_ip,
                'hotspot_status': 'Active' if hotspot_status.active else 'Stopped',
                'hotspot_ssid': hotspot_status.ssid if hotspot_status.active else None,
                'hotspot_ip': hotspot_status.ip_address if hotspot_status.active else None,
                'hotspot_clients': hotspot_status.clients if hotspot_status.active else 0,
                'interface': interface,
                'interface_ready': not hotspot_status.active
            }
        }
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"API: Error getting dashboard status: {e}")
        # Return a basic response even if there are errors
        return jsonify({
            'success': True,
            'timestamp': datetime.now().isoformat(),
            'dashboard': {
                'connection_status': 'Unknown',
                'current_network': None,
                'signal_strength': None,
                'signal_quality': None,
                'current_ip': None,
                'hotspot_status': 'Unknown',
                'hotspot_ssid': None,
                'hotspot_ip': None,
                'hotspot_clients': 0,
                'interface': 'wlan0',
                'interface_ready': True
            }
        })


@bp.route('/status/interface', methods=['GET'])
def get_interface_status():
    """
    Get wireless interface status and information
    
    Returns:
        JSON response with interface details
    """
    try:
        logger.info("API: Getting interface status...")
        
        connector = WiFiConnector()
        interface = connector.interface
        
        # Get current connection
        current_network = connector.get_current_connection()
        
        # Check interface availability
        interface_available, interface_status = connector.is_interface_available_for_hotspot()
        
        # Get interface IP addresses
        import subprocess
        ip_addresses = []
        try:
            result = subprocess.run(
                ['ip', '-4', 'addr', 'show', interface],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'inet ' in line:
                        ip = line.strip().split()[1]
                        ip_addresses.append(ip)
        except Exception:
            pass
        
        response = {
            'success': True,
            'interface': {
                'name': interface,
                'connected': current_network is not None,
                'current_network': current_network,
                'available': interface_available,
                'status': interface_status,
                'ip_addresses': ip_addresses
            },
            'timestamp': datetime.now().isoformat()
        }
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"API: Error getting interface status: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to get interface status: {str(e)}'
        }), 500


@bp.route('/status/services', methods=['GET'])
def get_services_status():
    """
    Get status of all PiBridge services
    
    Returns:
        JSON response with service status information
    """
    try:
        logger.info("API: Getting services status...")
        
        import subprocess
        
        services = ['pibridge-web.service', 'pibridge-auto-recovery.service', 'pibridge-hotspot.service']
        service_statuses = {}
        
        for service in services:
            try:
                # Check if service is enabled
                enabled_result = subprocess.run(
                    ['sudo', 'systemctl', 'is-enabled', service],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                enabled = enabled_result.returncode == 0 and 'enabled' in enabled_result.stdout
                
                # Check if service is active
                active_result = subprocess.run(
                    ['sudo', 'systemctl', 'is-active', service],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                active = active_result.returncode == 0 and 'active' in active_result.stdout
                
                service_statuses[service] = {
                    'enabled': enabled,
                    'active': active,
                    'available': True
                }
                
            except Exception as e:
                service_statuses[service] = {
                    'enabled': False,
                    'active': False,
                    'available': False,
                    'error': str(e)
                }
        
        response = {
            'success': True,
            'services': service_statuses,
            'timestamp': datetime.now().isoformat()
        }
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"API: Error getting services status: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to get services status: {str(e)}'
        }), 500