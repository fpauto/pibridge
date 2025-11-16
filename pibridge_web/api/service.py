"""
Service management API endpoints for PiBridge Web UI

Provides endpoints to manage web interface service and auto-recovery service.
"""

import sys
import os
from flask import Blueprint, jsonify, request
from datetime import datetime

# Add parent directory to path to import pibridge modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import PiBridge modules (modules are now at root level)
try:
    from logger import setup_logger
except ImportError as e:
    print(f"Warning: Could not import PiBridge modules: {e}")
    def setup_logger(*args, **kwargs): 
        return type('Logger', (), {'info': print, 'error': print, 'warning': print})()

bp = Blueprint('service', __name__)
logger = setup_logger(verbose=False, debug=False)


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


# Web Interface Service Management

@bp.route('/web/enable', methods=['POST'])
def enable_web_service():
    """
    Enable the web interface service (auto-start on boot)
    
    Returns:
        JSON response indicating success or failure
    """
    try:
        logger.info("API: Enabling web interface service...")
        
        # Create systemd service file
        service_content = f"""[Unit]
Description=PiBridge Web UI
After=network.target
Wants=network.target

[Service]
Type=simple
User=root
WorkingDirectory={os.path.dirname(os.path.dirname(os.path.abspath(__file__)))}
ExecStart=/usr/bin/python3 {os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'app.py')}
Restart=always
RestartSec=10
Environment=PIBRIDGE_WEB_HOST=0.0.0.0
Environment=PIBRIDGE_WEB_PORT=5000
Environment=PIBRIDGE_WEB_DEBUG=False

[Install]
WantedBy=multi-user.target
"""
        
        # Write service file
        service_file_path = '/tmp/pibridge-web.service'
        with open(service_file_path, 'w') as f:
            f.write(service_content)
        
        # Copy to systemd directory and enable
        success, message = run_systemctl_command('start', 'pibridge-web.service')
        if success:
            run_systemctl_command('enable', 'pibridge-web.service')
        else:
            # Service might not exist yet, create it
            try:
                import subprocess
                subprocess.run(['sudo', 'cp', service_file_path, '/etc/systemd/system/'], check=True)
                subprocess.run(['sudo', 'systemctl', 'daemon-reload'], check=True)
                run_systemctl_command('enable', 'pibridge-web.service')
                success, message = run_systemctl_command('start', 'pibridge-web.service')
            except Exception as e:
                success, message = False, f"Failed to create service: {str(e)}"
        
        if success:
            logger.info("API: Web interface service enabled successfully")
            return jsonify({
                'success': True,
                'message': 'Web interface service enabled successfully'
            })
        else:
            logger.error(f"API: Failed to enable web service: {message}")
            return jsonify({
                'success': False,
                'error': f'Failed to enable web service: {message}'
            }), 500
            
    except Exception as e:
        logger.error(f"API: Error enabling web service: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to enable web service: {str(e)}'
        }), 500


@bp.route('/web/disable', methods=['POST'])
def disable_web_service():
    """
    Disable the web interface service (prevent auto-start on boot)
    
    Returns:
        JSON response indicating success or failure
    """
    try:
        logger.info("API: Disabling web interface service...")
        
        # Stop service
        run_systemctl_command('stop', 'pibridge-web.service')
        
        # Disable service
        run_systemctl_command('disable', 'pibridge-web.service')
        
        logger.info("API: Web interface service disabled successfully")
        return jsonify({
            'success': True,
            'message': 'Web interface service disabled successfully'
        })
        
    except Exception as e:
        logger.error(f"API: Error disabling web service: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to disable web service: {str(e)}'
        }), 500


@bp.route('/web/start', methods=['POST'])
def start_web_service():
    """
    Start the web interface service (if enabled)
    
    Returns:
        JSON response indicating success or failure
    """
    try:
        logger.info("API: Starting web interface service...")
        
        success, message = run_systemctl_command('start', 'pibridge-web.service')
        
        if success:
            logger.info("API: Web interface service started successfully")
            return jsonify({
                'success': True,
                'message': 'Web interface service started successfully'
            })
        else:
            logger.error(f"API: Failed to start web service: {message}")
            return jsonify({
                'success': False,
                'error': f'Failed to start web service: {message}'
            }), 500
            
    except Exception as e:
        logger.error(f"API: Error starting web service: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to start web service: {str(e)}'
        }), 500


@bp.route('/web/stop', methods=['POST'])
def stop_web_service():
    """
    Stop the web interface service
    
    Returns:
        JSON response indicating success or failure
    """
    try:
        logger.info("API: Stopping web interface service...")
        
        success, message = run_systemctl_command('stop', 'pibridge-web.service')
        
        if success:
            logger.info("API: Web interface service stopped successfully")
            return jsonify({
                'success': True,
                'message': 'Web interface service stopped successfully'
            })
        else:
            logger.error(f"API: Failed to stop web service: {message}")
            return jsonify({
                'success': False,
                'error': f'Failed to stop web service: {message}'
            }), 500
            
    except Exception as e:
        logger.error(f"API: Error stopping web service: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to stop web service: {str(e)}'
        }), 500


@bp.route('/web/status', methods=['GET'])
def get_web_service_status():
    """
    Get web interface service status
    
    Returns:
        JSON response with service status information
    """
    try:
        logger.info("API: Getting web service status...")
        
        # Check if service is enabled
        enabled_success, _ = run_systemctl_command('is-enabled', 'pibridge-web.service')
        service_enabled = enabled_success
        
        # Check if service is active
        active_success, _ = run_systemctl_command('status', 'pibridge-web.service')
        service_active = active_success
        
        return jsonify({
            'success': True,
            'service': {
                'name': 'pibridge-web.service',
                'enabled': service_enabled,
                'active': service_active,
                'url': 'http://localhost:5000' if service_active else None
            }
        })
        
    except Exception as e:
        logger.error(f"API: Error getting web service status: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to get web service status: {str(e)}'
        }), 500


# Auto-Recovery Service Management

@bp.route('/auto-recovery/enable', methods=['POST'])
def enable_auto_recovery():
    """
    Enable the auto-recovery service (boot-time WiFi-to-hotspot fallback)
    
    Returns:
        JSON response indicating success or failure
    """
    try:
        logger.info("API: Enabling auto-recovery service...")
        
        # Create auto-recovery service
        pibridge_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        service_content = f"""[Unit]
Description=PiBridge Auto-Recovery Service
After=network.target
Wants=network.target

[Service]
Type=oneshot
RemainAfterExit=yes
User=root
ExecStart={pibridge_path}/auto_recovery.sh
TimeoutStartSec=300

[Install]
WantedBy=multi-user.target
"""
        
        # Create auto-recovery script
        pibridge_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        script_content = f"""#!/bin/bash
# PiBridge Auto-Recovery Script

# Configuration
PIBRIDGE_PATH="{pibridge_path}"
WIFI_TIMEOUT=30
CONNECT_TIMEOUT=30

# Log function
log() {{
    echo "[$(date)] PiBridge Auto-Recovery: $1"
    logger "PiBridge Auto-Recovery: $1"
}}

# Check if auto-recovery is enabled
if ! {pibridge_path}/venv/bin/python -m pibridge auto-recovery status | grep -q "enabled"; then
    log "Auto-recovery is disabled, exiting"
    exit 0
fi

log "Starting boot sequence"

# Wait for WiFi interface
log "Waiting for WiFi interface..."
for i in $(seq 1 $WIFI_TIMEOUT); do
    if ip link show | grep -q "wlan"; then
        log "WiFi interface found"
        break
    fi
    sleep 1
done

# Check interface again
if ! ip link show | grep -q "wlan"; then
    log "WiFi interface not found after {WIFI_TIMEOUT}s"
    exit 1
fi

# Attempt auto-connect
log "Attempting auto-connect..."
cd {pibridge_path}
if {pibridge_path}/venv/bin/python -m pibridge connect; then
    log "Auto-connect successful"
    exit 0
else
    log "Auto-connect failed, checking hotspot service..."
    
    # Check if hotspot service is enabled
    if {pibridge_path}/venv/bin/python -m pibridge hotspot service status | grep -q "enabled"; then
        log "Starting hotspot..."
        {pibridge_path}/venv/bin/python -m pibridge hotspot start
        log "Hotspot started"
    else
        log "Hotspot service is disabled"
    fi
fi
"""
        
        # Write service file
        service_file_path = '/tmp/pibridge-auto-recovery.service'
        with open(service_file_path, 'w') as f:
            f.write(service_content)
        
        # Write auto-recovery script
        script_path = f'{pibridge_path}/auto_recovery.sh'
        with open(script_path, 'w') as f:
            f.write(script_content)
        
        # Make script executable
        os.chmod(script_path, 0o755)
        
        # Create systemd service
        try:
            import subprocess
            subprocess.run(['sudo', 'cp', service_file_path, '/etc/systemd/system/'], check=True)
            subprocess.run(['sudo', 'systemctl', 'daemon-reload'], check=True)
            run_systemctl_command('enable', 'pibridge-auto-recovery.service')
            logger.info("API: Auto-recovery service created successfully")
        except Exception as e:
            logger.error(f"API: Failed to create auto-recovery service: {e}")
            return jsonify({
                'success': False,
                'error': f'Failed to create auto-recovery service: {str(e)}'
            }), 500
        
        logger.info("API: Auto-recovery service enabled successfully")
        return jsonify({
            'success': True,
            'message': 'Auto-recovery service enabled successfully'
        })
        
    except Exception as e:
        logger.error(f"API: Error enabling auto-recovery: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to enable auto-recovery: {str(e)}'
        }), 500


@bp.route('/auto-recovery/disable', methods=['POST'])
def disable_auto_recovery():
    """
    Disable the auto-recovery service
    
    Returns:
        JSON response indicating success or failure
    """
    try:
        logger.info("API: Disabling auto-recovery service...")
        
        # Disable service
        run_systemctl_command('disable', 'pibridge-auto-recovery.service')
        
        logger.info("API: Auto-recovery service disabled successfully")
        return jsonify({
            'success': True,
            'message': 'Auto-recovery service disabled successfully'
        })
        
    except Exception as e:
        logger.error(f"API: Error disabling auto-recovery: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to disable auto-recovery: {str(e)}'
        }), 500


@bp.route('/auto-recovery/status', methods=['GET'])
def get_auto_recovery_status():
    """
    Get auto-recovery service status
    
    Returns:
        JSON response with service status information
    """
    try:
        logger.info("API: Getting auto-recovery service status...")
        
        # Check if service is enabled
        enabled_success, _ = run_systemctl_command('is-enabled', 'pibridge-auto-recovery.service')
        service_enabled = enabled_success
        
        # Auto-recovery is a oneshot service, so it's "active" if enabled
        return jsonify({
            'success': True,
            'service': {
                'name': 'pibridge-auto-recovery.service',
                'enabled': service_enabled,
                'active': service_enabled,  # oneshot service shows as active when enabled
                'description': 'Boot-time WiFi-to-hotspot fallback service'
            }
        })
        
    except Exception as e:
        logger.error(f"API: Error getting auto-recovery service status: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to get auto-recovery service status: {str(e)}'
        }), 500