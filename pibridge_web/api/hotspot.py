"""
Hotspot management API endpoints for PiBridge Web UI

Provides endpoints to start/stop WiFi hotspot and manage hotspot service.
"""

import sys
import os
from flask import Blueprint, jsonify, request
from datetime import datetime

# Add parent directory to path to import pibridge modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import PiBridge modules (modules are now at root level)
try:
    from hotspot import HotspotManager, HotspotStatus
    from rfkill_checker import check_rfkill
    from logger import setup_logger
    from exceptions import RfkillBlockedException
except ImportError as e:
    print(f"Warning: Could not import PiBridge modules: {e}")
    # Mock classes for development
    class HotspotManager:
        def start_hotspot(self): return True
        def stop_hotspot(self): return True
        def get_status(self):
            class MockStatus:
                active = False
                ssid = "pibridge"
                interface = "wlan0"
                ip_address = "192.168.4.1"
                clients = 0
            return MockStatus()
        def get_interface(self): return "wlan0"
    
    class HotspotStatus:
        active = False
        ssid = "pibridge"
        interface = "wlan0"
        ip_address = "192.168.4.1"
        clients = 0
    
    def check_rfkill(): pass
    
    def setup_logger(*args, **kwargs): 
        return type('Logger', (), {'info': print, 'error': print, 'warning': print})()

bp = Blueprint('hotspot', __name__)
logger = setup_logger(verbose=False, debug=False)


@bp.route('/hotspot/start', methods=['POST'])
def start_hotspot():
    """
    Start the WiFi hotspot
    
    Returns:
        JSON response indicating success or failure
    """
    try:
        logger.info("API: Starting WiFi hotspot...")
        
        # Check rfkill status
        try:
            check_rfkill()
        except RfkillBlockedException as e:
            return jsonify({
                'success': False,
                'error': f'Wireless is blocked: {str(e)}'
            }), 400
        # Start hotspot
        hotspot = HotspotManager()
        success = hotspot.start_hotspot()
        
        if success:
            status = hotspot.get_status()
            logger.info(f"API: Hotspot started successfully")
            
            return jsonify({
                'success': True,
                'message': 'Hotspot started successfully',
                'hotspot': {
                    'ssid': status.ssid,
                    'interface': status.interface,
                    'ip_address': status.ip_address,
                    'active': True
                }
            })
        else:
            logger.error("API: Failed to start hotspot")
            return jsonify({
                'success': False,
                'error': 'Failed to start hotspot'
            }), 500
            
    except Exception as e:
        error_msg = str(e)
        logger.error(f"API: Error starting hotspot: {e}")
        
        # Provide more helpful error messages based on the type of error
        if "sudo" in error_msg.lower() or "permission" in error_msg.lower() or "operation not permitted" in error_msg.lower():
            user_message = "Hotspot functionality requires administrator privileges. Please run the web interface as root or contact your system administrator."
            status_code = 403  # Forbidden
        elif "hard_blocked" in error_msg.lower() or "soft_blocked" in error_msg.lower():
            user_message = "Wireless adapter is blocked. Please unblock it using 'sudo rfkill unblock wifi' and try again."
            status_code = 400  # Bad Request
        elif "already running" in error_msg.lower():
            user_message = "Hotspot is already running. Stop it first before starting again."
            status_code = 409  # Conflict
        else:
            user_message = f"Failed to start hotspot: {error_msg}"
            status_code = 500  # Internal Server Error
        
        return jsonify({
            'success': False,
            'error': user_message,
            'debug_info': error_msg if status_code == 500 else None
        }), status_code


@bp.route('/hotspot/stop', methods=['POST'])
def stop_hotspot():
    """
    Stop the WiFi hotspot
    
    Returns:
        JSON response indicating success or failure
    """
    try:
        logger.info("API: Stopping WiFi hotspot...")
        
        hotspot = HotspotManager()
        success = hotspot.stop_hotspot()
        
        if success:
            logger.info("API: Hotspot stopped successfully")
            
            return jsonify({
                'success': True,
                'message': 'Hotspot stopped successfully',
                'interface_ready': True
            })
        else:
            logger.error("API: Failed to stop hotspot")
            return jsonify({
                'success': False,
                'error': 'Failed to stop hotspot'
            }), 500
            
    except Exception as e:
        logger.error(f"API: Error stopping hotspot: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to stop hotspot: {str(e)}'
        }), 500


@bp.route('/hotspot/status', methods=['GET'])
def get_hotspot_status():
    """
    Get current hotspot status
    
    Returns:
        JSON response with hotspot status information
    """
    try:
        logger.info("API: Getting hotspot status...")
        
        hotspot = HotspotManager()
        status = hotspot.get_status()
        
        response = {
            'success': True,
            'hotspot': {
                'active': status.active,
                'ssid': status.ssid,
                'interface': status.interface,
                'ip_address': status.ip_address,
                'clients': status.clients
            },
            'timestamp': datetime.now().isoformat()
        }
        
        # Add client details if available - try both methods
        client_details = None
        try:
            # First try the HotspotManager method
            client_details = hotspot.get_connected_clients()
        except Exception:
            pass
        
        # If the manager method didn't work, try direct lease file reading
        if not client_details and status.clients > 0:
            try:
                import subprocess
                result = subprocess.run(
                    ['sudo', 'cat', '/var/lib/misc/dnsmasq.leases'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if result.returncode == 0:
                    clients = []
                    leases = [line for line in result.stdout.split('\n') if line]
                    for lease in leases:
                        parts = lease.split()
                        if len(parts) >= 3:
                            timestamp, mac, ip = parts[0], parts[1], parts[2]
                            hostname = parts[3] if len(parts) > 3 else 'unknown'
                            
                            clients.append({
                                'mac': mac,
                                'ip': ip,
                                'hostname': hostname,
                                'connected_since': hotspot._format_timestamp(int(timestamp)) if timestamp.isdigit() else 'unknown'
                            })
                    
                    client_details = clients
            except Exception:
                pass  # Client details are optional
        
        if client_details:
            response['hotspot']['client_details'] = client_details
        
        logger.info(f"API: Hotspot status: {'active' if status.active else 'inactive'}")
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"API: Error getting hotspot status: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to get hotspot status: {str(e)}'
        }), 500


@bp.route('/hotspot/service/enable', methods=['POST'])
def enable_hotspot_service():
    """
    Enable the hotspot service (allows hotspot to start automatically)
    
    Returns:
        JSON response indicating success or failure
    """
    try:
        logger.info("API: Enabling hotspot service...")
        
        import subprocess
        
        # Get the correct pibridge path
        import os
        pibridge_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

        # Create systemd service file
        service_content = f"""[Unit]
Description=PiBridge WiFi Hotspot
After=network.target
Wants=network.target

[Service]
Type=simple
User=root
ExecStart=/usr/bin/python3 -m pibridge hotspot start
WorkingDirectory={pibridge_path}
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
"""
        
        # Write service file
        with open('/tmp/pibridge-hotspot.service', 'w') as f:
            f.write(service_content)
        
        # Copy to systemd directory
        result = subprocess.run(
            ['sudo', 'cp', '/tmp/pibridge-hotspot.service', '/etc/systemd/system/'],
            capture_output=True
        )
        
        if result.returncode == 0:
            # Reload systemd and enable service
            subprocess.run(['sudo', 'systemctl', 'daemon-reload'], check=False)
            subprocess.run(['sudo', 'systemctl', 'enable', 'pibridge-hotspot.service'], check=False)
            
            logger.info("API: Hotspot service enabled successfully")
            return jsonify({
                'success': True,
                'message': 'Hotspot service enabled successfully'
            })
        else:
            logger.error("API: Failed to create hotspot service")
            return jsonify({
                'success': False,
                'error': 'Failed to enable hotspot service'
            }), 500
            
    except Exception as e:
        logger.error(f"API: Error enabling hotspot service: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to enable hotspot service: {str(e)}'
        }), 500


@bp.route('/hotspot/service/disable', methods=['POST'])
def disable_hotspot_service():
    """
    Disable the hotspot service (prevents automatic hotspot start)
    
    Returns:
        JSON response indicating success or failure
    """
    try:
        logger.info("API: Disabling hotspot service...")
        
        import subprocess
        
        # Stop and disable service
        subprocess.run(['sudo', 'systemctl', 'stop', 'pibridge-hotspot.service'], check=False)
        subprocess.run(['sudo', 'systemctl', 'disable', 'pibridge-hotspot.service'], check=False)
        
        # Remove service file
        subprocess.run(['sudo', 'rm', '-f', '/etc/systemd/system/pibridge-hotspot.service'], check=False)
        
        # Reload systemd
        subprocess.run(['sudo', 'systemctl', 'daemon-reload'], check=False)
        
        logger.info("API: Hotspot service disabled successfully")
        return jsonify({
            'success': True,
            'message': 'Hotspot service disabled successfully'
        })
        
    except Exception as e:
        logger.error(f"API: Error disabling hotspot service: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to disable hotspot service: {str(e)}'
        }), 500


@bp.route('/hotspot/service/status', methods=['GET'])
def get_hotspot_service_status():
    """
    Get hotspot service status
    
    Returns:
        JSON response with service status information
    """
    try:
        logger.info("API: Getting hotspot service status...")
        
        import subprocess
        
        # Check if service is enabled
        enabled_result = subprocess.run(
            ['sudo', 'systemctl', 'is-enabled', 'pibridge-hotspot.service'],
            capture_output=True,
            text=True
        )
        
        # Check if service is active
        active_result = subprocess.run(
            ['sudo', 'systemctl', 'is-active', 'pibridge-hotspot.service'],
            capture_output=True,
            text=True
        )
        
        service_enabled = enabled_result.returncode == 0 and 'enabled' in enabled_result.stdout
        service_active = active_result.returncode == 0 and 'active' in active_result.stdout
        
        return jsonify({
            'success': True,
            'service': {
                'enabled': service_enabled,
                'active': service_active,
                'name': 'pibridge-hotspot.service'
            }
        })
        
    except Exception as e:
        logger.error(f"API: Error getting hotspot service status: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to get hotspot service status: {str(e)}'
        }), 500