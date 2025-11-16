"""
Bridge management API endpoints for PiBridge Web UI

Provides endpoints to manage TCP to Serial bridge profiles, services, and device scanning.
"""

import sys
import os
from flask import Blueprint, jsonify, request
from datetime import datetime

# Add parent directory to path to import pibridge modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import PiBridge modules (modules are now at root level)
try:
    from tcp2com_pyserial import PySerialTCP2COMManager
    from logger import setup_logger
    
    # Mock TCP2COMManager for compatibility (tcp2com module doesn't exist)
    class TCP2COMManager:
        def list_profiles(self): return {}
        def add_profile(self, name, socat_command, description=""): pass
        def remove_profile(self, name): pass
        def update_socat_command(self, name, new_command, description=None): pass
        def start_bridge(self, profile_name=None): return True
        def stop_bridge(self): return True
        def restart_bridge(self, profile_name=None): return True
        def is_active(self): return False
        def get_status(self): return type('Status', (), {'active': False, 'pid': None, 'command': None})()
        
except ImportError as e:
    print(f"Warning: Could not import PiBridge modules: {e}")
    def setup_logger(*args, **kwargs):
        return type('Logger', (), {'info': print, 'error': print, 'warning': print})()
    
    # Mock classes for development
    class PySerialTCP2COMManager:
        def list_profiles(self): return {}
        def add_profile(self, name, device, baudrate, port, **kwargs): pass
        def remove_profile(self, name): pass
        def update_profile(self, name, **kwargs): pass
        def list_serial_devices(self): return []
        def start_bridge(self, profile_name=None): return True
        def stop_bridge(self): return True
        def restart_bridge(self, profile_name=None): return True
        def is_active(self): return False
        def get_status(self): return type('Status', (), {'active': False, 'port': None, 'device': None})()
    
    class TCP2COMManager:
        def list_profiles(self): return {}
        def add_profile(self, name, socat_command, description=""): pass
        def remove_profile(self, name): pass
        def update_socat_command(self, name, new_command, description=None): pass
        def start_bridge(self, profile_name=None): return True
        def stop_bridge(self): return True
        def restart_bridge(self, profile_name=None): return True
        def is_active(self): return False
        def get_status(self): return type('Status', (), {'active': False, 'pid': None, 'command': None})()

bp = Blueprint('bridge', __name__)
logger = setup_logger(verbose=False, debug=False)

# Global bridge managers
pyserial_manager = PySerialTCP2COMManager()
tcp2com_manager = TCP2COMManager()


def run_systemctl_command(action, service_name):
    """Helper function to run systemctl commands"""
    import subprocess
    
    try:
        if action == 'start':
            result = subprocess.run(
                ['sudo', 'systemctl', 'start', service_name],
                capture_output=True,
                text=True,
                timeout=30
            )
        elif action == 'stop':
            result = subprocess.run(
                ['sudo', 'systemctl', 'stop', service_name],
                capture_output=True,
                text=True,
                timeout=30
            )
        elif action == 'restart':
            result = subprocess.run(
                ['sudo', 'systemctl', 'restart', service_name],
                capture_output=True,
                text=True,
                timeout=30
            )
        elif action == 'status':
            result = subprocess.run(
                ['sudo', 'systemctl', 'is-active', service_name],
                capture_output=True,
                text=True,
                timeout=10
            )
        elif action == 'enable':
            result = subprocess.run(
                ['sudo', 'systemctl', 'enable', service_name],
                capture_output=True,
                text=True,
                timeout=30
            )
        elif action == 'disable':
            result = subprocess.run(
                ['sudo', 'systemctl', 'disable', service_name],
                capture_output=True,
                text=True,
                timeout=30
            )
        elif action == 'is-enabled':
            result = subprocess.run(
                ['sudo', 'systemctl', 'is-enabled', service_name],
                capture_output=True,
                text=True,
                timeout=10
            )
        else:
            return False, f"Unknown action: {action}"
        
        if result.returncode == 0:
            return True, "Success"
        else:
            error_msg = result.stderr.strip() if result.stderr else "Unknown error"
            return False, error_msg
            
    except subprocess.TimeoutExpired:
        return False, f"Command timeout after 30 seconds"
    except Exception as e:
        return False, f"Error running systemctl: {str(e)}"


# PySerial TCP2COM Management

@bp.route('/pyserial/profiles', methods=['GET'])
def list_pyserial_profiles():
    """
    List all PySerial TCP2COM profiles
    
    Returns:
        JSON response with profile information
    """
    try:
        logger.info("API: Listing PySerial TCP2COM profiles...")
        
        profiles = pyserial_manager.list_profiles()
        status = pyserial_manager.get_status()
        
        return jsonify({
            'success': True,
            'bridge_type': 'pyserial',
            'active': status.active,
            'profiles': profiles
        })
        
    except Exception as e:
        logger.error(f"API: Error listing PySerial profiles: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to list profiles: {str(e)}'
        }), 500


@bp.route('/pyserial/profiles', methods=['POST'])
def add_pyserial_profile():
    """
    Add a new PySerial TCP2COM profile
    
    JSON body:
        - name: Profile name (required)
        - device: Serial device path (required)
        - baudrate: Baud rate (default: 9600)
        - port: TCP port (required)
        - bytesize: Data bits (default: 8)
        - parity: Parity (default: 'N')
        - stopbits: Stop bits (default: 1)
        - timeout: Timeout in seconds (default: 1)
        - description: Optional description
        
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
        
        # Validate required fields
        required_fields = ['name', 'device', 'port']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'success': False,
                    'error': f'Field "{field}" is required'
                }), 400
        
        name = data['name'].strip()
        device = data['device'].strip()
        port = int(data['port'])
        baudrate = int(data.get('baudrate', 9600))
        bytesize = int(data.get('bytesize', 8))
        parity = data.get('parity', 'N').upper()
        stopbits = int(data.get('stopbits', 1))
        timeout = float(data.get('timeout', 1.0))
        description = data.get('description', '').strip()
        
        logger.info(f"API: Adding PySerial profile '{name}'...")
        
        pyserial_manager.add_profile(
            name=name,
            device=device,
            baudrate=baudrate,
            port=port,
            bytesize=bytesize,
            parity=parity,
            stopbits=stopbits,
            timeout=timeout,
            description=description
        )
        
        logger.info(f"API: Successfully added PySerial profile '{name}'")
        return jsonify({
            'success': True,
            'message': f'Profile "{name}" created successfully'
        })
        
    except Exception as e:
        logger.error(f"API: Error adding PySerial profile: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to add profile: {str(e)}'
        }), 500


@bp.route('/pyserial/profiles/<name>', methods=['PUT'])
def update_pyserial_profile(name):
    """
    Update an existing PySerial TCP2COM profile
    
    URL parameter:
        - name: Profile name
        
    JSON body: Fields to update (any of: device, baudrate, port, bytesize, parity, stopbits, timeout, description)
        
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
        
        logger.info(f"API: Updating PySerial profile '{name}'...")
        
        # Convert numeric fields
        update_data = {}
        for field in ['baudrate', 'port', 'bytesize', 'stopbits', 'timeout']:
            if field in data:
                update_data[field] = int(data[field]) if field in ['baudrate', 'port', 'bytesize', 'stopbits'] else float(data[field])
        
        # Handle string fields
        for field in ['device', 'parity', 'description']:
            if field in data:
                update_data[field] = data[field].strip().upper() if field == 'parity' else data[field].strip()
        
        pyserial_manager.update_profile(name, **update_data)
        
        logger.info(f"API: Successfully updated PySerial profile '{name}'")
        return jsonify({
            'success': True,
            'message': f'Profile "{name}" updated successfully'
        })
        
    except Exception as e:
        logger.error(f"API: Error updating PySerial profile: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to update profile: {str(e)}'
        }), 500


@bp.route('/pyserial/profiles/<name>', methods=['DELETE'])
def delete_pyserial_profile(name):
    """
    Delete a PySerial TCP2COM profile
    
    URL parameter:
        - name: Profile name
        
    Returns:
        JSON response indicating success or failure
    """
    try:
        logger.info(f"API: Deleting PySerial profile '{name}'...")
        
        pyserial_manager.remove_profile(name)
        
        logger.info(f"API: Successfully deleted PySerial profile '{name}'")
        return jsonify({
            'success': True,
            'message': f'Profile "{name}" deleted successfully'
        })
        
    except Exception as e:
        logger.error(f"API: Error deleting PySerial profile: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to delete profile: {str(e)}'
        }), 500


@bp.route('/pyserial/devices', methods=['GET'])
def list_serial_devices():
    """
    List available serial devices
    
    Returns:
        JSON response with available serial devices
    """
    try:
        logger.info("API: Listing serial devices...")
        
        devices = pyserial_manager.list_serial_devices()
        
        return jsonify({
            'success': True,
            'devices': devices,
            'count': len(devices)
        })
        
    except Exception as e:
        logger.error(f"API: Error listing serial devices: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to list devices: {str(e)}'
        }), 500


@bp.route('/pyserial/start', methods=['POST'])
def start_pyserial_bridge():
    """
    Start the PySerial TCP2COM bridge
    
    JSON body:
        - profile: Profile name (optional, defaults to 'default')
        
    Returns:
        JSON response indicating success or failure
    """
    try:
        data = request.get_json() or {}
        profile = data.get('profile', 'default')
        
        logger.info(f"API: Starting PySerial bridge with profile '{profile}'...")
        
        success = pyserial_manager.start_bridge(profile)
        
        if success:
            logger.info(f"API: Successfully started PySerial bridge with profile '{profile}'")
            return jsonify({
                'success': True,
                'message': f'Bridge started successfully with profile "{profile}"'
            })
        else:
            # Enhanced error detection and reporting
            try:
                # Check if the profile exists
                profile_data = pyserial_manager.get_profile(profile)
                if not profile_data:
                    error_msg = f'Bridge profile "{profile}" not found'
                else:
                    device = profile_data.get('device', 'Unknown device')
                    # Check if the serial device exists
                    import os
                    if not os.path.exists(device):
                        error_msg = f'Serial device "{device}" not found. Please check if the USB device is connected and the profile is correctly configured.'
                    else:
                        error_msg = f'Failed to start bridge with profile "{profile}". Check device permissions and port availability.'
            except Exception:
                error_msg = f'Failed to start bridge with profile "{profile}"'
            
            logger.error(f"API: {error_msg}")
            return jsonify({
                'success': False,
                'error': error_msg,
                'troubleshooting': {
                    'check_device': 'Verify the serial device exists (e.g., /dev/ttyUSB0)',
                    'check_permissions': 'Ensure the user has permissions to access the serial device',
                    'check_usb': 'Connect the USB device and ensure drivers are installed',
                    'check_profile': 'Consider updating the profile to use a different device'
                }
            }), 500
            
    except Exception as e:
        logger.error(f"API: Error starting PySerial bridge: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to start bridge: {str(e)}'
        }), 500


@bp.route('/pyserial/stop', methods=['POST'])
def stop_pyserial_bridge():
    """
    Stop the PySerial TCP2COM bridge
    
    Returns:
        JSON response indicating success or failure
    """
    try:
        logger.info("API: Stopping PySerial bridge...")
        
        success = pyserial_manager.stop_bridge()
        
        if success:
            logger.info("API: Successfully stopped PySerial bridge")
            return jsonify({
                'success': True,
                'message': 'Bridge stopped successfully'
            })
        else:
            logger.error("API: Failed to stop PySerial bridge")
            return jsonify({
                'success': False,
                'error': 'Failed to stop bridge'
            }), 500
            
    except Exception as e:
        logger.error(f"API: Error stopping PySerial bridge: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to stop bridge: {str(e)}'
        }), 500


@bp.route('/pyserial/status', methods=['GET'])
def get_pyserial_status():
    """
    Get PySerial TCP2COM bridge status
    
    Returns:
        JSON response with bridge status information
    """
    try:
        logger.info("API: Getting PySerial bridge status...")
        
        status = pyserial_manager.get_status()
        
        return jsonify({
            'success': True,
            'bridge_type': 'pyserial',
            'active': status.active,
            'port': status.port,
            'device': getattr(status, 'device', None)
        })
        
    except Exception as e:
        logger.error(f"API: Error getting PySerial bridge status: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to get status: {str(e)}'
        }), 500


# TCP2COM Management

@bp.route('/tcp2com/profiles', methods=['GET'])
def list_tcp2com_profiles():
    """
    List all TCP2COM profiles
    
    Returns:
        JSON response with profile information
    """
    try:
        logger.info("API: Listing TCP2COM profiles...")
        
        profiles = tcp2com_manager.list_profiles()
        status = tcp2com_manager.get_status()
        
        return jsonify({
            'success': True,
            'bridge_type': 'tcp2com',
            'active': status.active,
            'profiles': profiles
        })
        
    except Exception as e:
        logger.error(f"API: Error listing TCP2COM profiles: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to list profiles: {str(e)}'
        }), 500


@bp.route('/tcp2com/profiles', methods=['POST'])
def add_tcp2com_profile():
    """
    Add a new TCP2COM profile
    
    JSON body:
        - name: Profile name (required)
        - socat_command: Socat command (required)
        - description: Optional description
        
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
        
        name = data.get('name', '').strip()
        socat_command = data.get('socat_command', '').strip()
        description = data.get('description', '').strip()
        
        if not name or not socat_command:
            return jsonify({
                'success': False,
                'error': 'Profile name and socat command are required'
            }), 400
        
        logger.info(f"API: Adding TCP2COM profile '{name}'...")
        
        tcp2com_manager.add_profile(name, socat_command, description)
        
        logger.info(f"API: Successfully added TCP2COM profile '{name}'")
        return jsonify({
            'success': True,
            'message': f'Profile "{name}" created successfully'
        })
        
    except Exception as e:
        logger.error(f"API: Error adding TCP2COM profile: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to add profile: {str(e)}'
        }), 500


@bp.route('/tcp2com/profiles/<name>', methods=['PUT'])
def update_tcp2com_profile(name):
    """
    Update an existing TCP2COM profile
    
    URL parameter:
        - name: Profile name
        
    JSON body: Fields to update (socat_command and/or description)
        
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
        
        socat_command = data.get('socat_command')
        description = data.get('description')
        
        if not socat_command and not description:
            return jsonify({
                'success': False,
                'error': 'At least one field (socat_command or description) must be provided'
            }), 400
        
        logger.info(f"API: Updating TCP2COM profile '{name}'...")
        
        tcp2com_manager.update_socat_command(name, socat_command, description)
        
        logger.info(f"API: Successfully updated TCP2COM profile '{name}'")
        return jsonify({
            'success': True,
            'message': f'Profile "{name}" updated successfully'
        })
        
    except Exception as e:
        logger.error(f"API: Error updating TCP2COM profile: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to update profile: {str(e)}'
        }), 500


@bp.route('/tcp2com/profiles/<name>', methods=['DELETE'])
def delete_tcp2com_profile(name):
    """
    Delete a TCP2COM profile
    
    URL parameter:
        - name: Profile name
        
    Returns:
        JSON response indicating success or failure
    """
    try:
        logger.info(f"API: Deleting TCP2COM profile '{name}'...")
        
        tcp2com_manager.remove_profile(name)
        
        logger.info(f"API: Successfully deleted TCP2COM profile '{name}'")
        return jsonify({
            'success': True,
            'message': f'Profile "{name}" deleted successfully'
        })
        
    except Exception as e:
        logger.error(f"API: Error deleting TCP2COM profile: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to delete profile: {str(e)}'
        }), 500


@bp.route('/tcp2com/start', methods=['POST'])
def start_tcp2com_bridge():
    """
    Start the TCP2COM bridge
    
    JSON body:
        - profile: Profile name (optional, defaults to 'default')
        
    Returns:
        JSON response indicating success or failure
    """
    try:
        data = request.get_json() or {}
        profile = data.get('profile', 'default')
        
        logger.info(f"API: Starting TCP2COM bridge with profile '{profile}'...")
        
        success = tcp2com_manager.start_bridge(profile)
        
        if success:
            logger.info(f"API: Successfully started TCP2COM bridge with profile '{profile}'")
            return jsonify({
                'success': True,
                'message': f'Bridge started successfully with profile "{profile}"'
            })
        else:
            logger.error(f"API: Failed to start TCP2COM bridge with profile '{profile}'")
            return jsonify({
                'success': False,
                'error': f'Failed to start bridge with profile "{profile}"'
            }), 500
            
    except Exception as e:
        logger.error(f"API: Error starting TCP2COM bridge: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to start bridge: {str(e)}'
        }), 500


@bp.route('/tcp2com/stop', methods=['POST'])
def stop_tcp2com_bridge():
    """
    Stop the TCP2COM bridge
    
    Returns:
        JSON response indicating success or failure
    """
    try:
        logger.info("API: Stopping TCP2COM bridge...")
        
        success = tcp2com_manager.stop_bridge()
        
        if success:
            logger.info("API: Successfully stopped TCP2COM bridge")
            return jsonify({
                'success': True,
                'message': 'Bridge stopped successfully'
            })
        else:
            logger.error("API: Failed to stop TCP2COM bridge")
            return jsonify({
                'success': False,
                'error': 'Failed to stop bridge'
            }), 500
            
    except Exception as e:
        logger.error(f"API: Error stopping TCP2COM bridge: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to stop bridge: {str(e)}'
        }), 500


@bp.route('/tcp2com/status', methods=['GET'])
def get_tcp2com_status():
    """
    Get TCP2COM bridge status
    
    Returns:
        JSON response with bridge status information
    """
    try:
        logger.info("API: Getting TCP2COM bridge status...")
        
        status = tcp2com_manager.get_status()
        
        return jsonify({
            'success': True,
            'bridge_type': 'tcp2com',
            'active': status.active,
            'pid': status.pid,
            'command': getattr(status, 'command', None)
        })
        
    except Exception as e:
        logger.error(f"API: Error getting TCP2COM bridge status: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to get status: {str(e)}'
        }), 500


# Bridge Service Management

@bp.route('/pyserial/service/enable', methods=['POST'])
def enable_pyserial_service():
    """
    Enable PySerial TCP2COM service for auto-start on boot
    
    Returns:
        JSON response indicating success or failure
    """
    try:
        logger.info("API: Enabling PySerial TCP2COM service...")
        
        # Create systemd service file
        service_content = """[Unit]
Description=PiBridge PySerial TCP2COM Bridge
After=network.target
Wants=network.target

[Service]
Type=simple
User=root
WorkingDirectory={pibridge_path}
ExecStart=/usr/bin/python3 -m pibridge pyserial-tcp2com service start
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
""".format(pibridge_path=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        # Write service file
        service_file_path = '/tmp/pibridge-pyserial-tcp2com.service'
        with open(service_file_path, 'w') as f:
            f.write(service_content)
        
        # Create systemd service
        try:
            import subprocess
            subprocess.run(['sudo', 'cp', service_file_path, '/etc/systemd/system/'], check=True)
            subprocess.run(['sudo', 'systemctl', 'daemon-reload'], check=True)
            success, message = run_systemctl_command('enable', 'pibridge-pyserial-tcp2com.service')
            
            if success:
                logger.info("API: PySerial TCP2COM service enabled successfully")
                return jsonify({
                    'success': True,
                    'message': 'PySerial TCP2COM service enabled successfully'
                })
            else:
                logger.error(f"API: Failed to enable PySerial service: {message}")
                return jsonify({
                    'success': False,
                    'error': f'Failed to enable service: {message}'
                }), 500
                
        except Exception as e:
            logger.error(f"API: Failed to create PySerial service: {e}")
            return jsonify({
                'success': False,
                'error': f'Failed to create service: {str(e)}'
            }), 500
        
    except Exception as e:
        logger.error(f"API: Error enabling PySerial service: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to enable service: {str(e)}'
        }), 500


@bp.route('/pyserial/service/disable', methods=['POST'])
def disable_pyserial_service():
    """
    Disable PySerial TCP2COM service
    
    Returns:
        JSON response indicating success or failure
    """
    try:
        logger.info("API: Disabling PySerial TCP2COM service...")
        
        success, message = run_systemctl_command('disable', 'pibridge-pyserial-tcp2com.service')
        
        if success:
            logger.info("API: PySerial TCP2COM service disabled successfully")
            return jsonify({
                'success': True,
                'message': 'PySerial TCP2COM service disabled successfully'
            })
        else:
            logger.error(f"API: Failed to disable PySerial service: {message}")
            return jsonify({
                'success': False,
                'error': f'Failed to disable service: {message}'
            }), 500
            
    except Exception as e:
        logger.error(f"API: Error disabling PySerial service: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to disable service: {str(e)}'
        }), 500


@bp.route('/pyserial/service/status', methods=['GET'])
def get_pyserial_service_status():
    """
    Get PySerial TCP2COM service status
    
    Returns:
        JSON response with service status information
    """
    try:
        logger.info("API: Getting PySerial service status...")
        
        # Check if service is enabled
        enabled_success, _ = run_systemctl_command('is-enabled', 'pibridge-pyserial-tcp2com.service')
        service_enabled = enabled_success
        
        # Check if service is active
        active_success, _ = run_systemctl_command('status', 'pibridge-pyserial-tcp2com.service')
        service_active = active_success
        
        return jsonify({
            'success': True,
            'service': {
                'name': 'pibridge-pyserial-tcp2com.service',
                'enabled': service_enabled,
                'active': service_active
            }
        })
        
    except Exception as e:
        logger.error(f"API: Error getting PySerial service status: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to get service status: {str(e)}'
        }), 500