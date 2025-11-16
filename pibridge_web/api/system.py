"""
System control API endpoints for PiBridge Web UI

Provides endpoints for system control operations like reboot and shutdown.
"""

import sys
import os
from flask import Blueprint, jsonify, request
from datetime import datetime
import subprocess

# Add parent directory to path to import pibridge modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Initialize logger
try:
    from logger import setup_logger
    logger = setup_logger(verbose=False, debug=False)
except ImportError:
    import logging
    logger = logging.getLogger('pibridge-web-system')
    logger.addHandler(logging.StreamHandler())
    logger.setLevel(logging.INFO)

bp = Blueprint('system', __name__)


def run_system_command(command, timeout=30):
    """Helper function to run system commands with sudo"""
    try:
        result = subprocess.run(
            ['sudo'] + command,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Command timeout"
    except Exception as e:
        return False, "", str(e)


@bp.route('/system/reboot', methods=['POST'])
def system_reboot():
    """
    Reboot the system
    
    Returns:
        JSON response indicating success or failure
    """
    try:
        logger.info("API: System reboot requested...")
        
        # Check for confirmation parameter
        data = request.get_json() or {}
        if not data.get('confirm', False):
            return jsonify({
                'success': False,
                'error': 'Reboot confirmation required'
            }), 400
        
        # Run reboot command
        success, stdout, stderr = run_system_command(['reboot'])
        
        if success:
            logger.info("API: Reboot command executed successfully")
            return jsonify({
                'success': True,
                'message': 'System will reboot in 30 seconds'
            })
        else:
            logger.error(f"API: Reboot failed: {stderr}")
            return jsonify({
                'success': False,
                'error': f'Reboot failed: {stderr}'
            }), 500
            
    except Exception as e:
        logger.error(f"API: Error during reboot: {e}")
        return jsonify({
            'success': False,
            'error': f'Reboot error: {str(e)}'
        }), 500


@bp.route('/system/shutdown', methods=['POST'])
def system_shutdown():
    """
    Shutdown the system
    
    Returns:
        JSON response indicating success or failure
    """
    try:
        logger.info("API: System shutdown requested...")
        
        # Check for confirmation parameter
        data = request.get_json() or {}
        if not data.get('confirm', False):
            return jsonify({
                'success': False,
                'error': 'Shutdown confirmation required'
            }), 400
        
        # Run shutdown command
        success, stdout, stderr = run_system_command(['shutdown', '-h', 'now'])
        
        if success:
            logger.info("API: Shutdown command executed successfully")
            return jsonify({
                'success': True,
                'message': 'System will shutdown in 30 seconds'
            })
        else:
            logger.error(f"API: Shutdown failed: {stderr}")
            return jsonify({
                'success': False,
                'error': f'Shutdown failed: {stderr}'
            }), 500
            
    except Exception as e:
        logger.error(f"API: Error during shutdown: {e}")
        return jsonify({
            'success': False,
            'error': f'Shutdown error: {str(e)}'
        }), 500


@bp.route('/system/status', methods=['GET'])
def system_status():
    """
    Get system status information
    
    Returns:
        JSON response with system information
    """
    try:
        # Get uptime
        try:
            with open('/proc/uptime', 'r') as f:
                uptime_seconds = float(f.readline().split()[0])
            uptime_hours = uptime_seconds / 3600
            uptime_str = f"{uptime_hours:.1f} hours"
        except Exception:
            uptime_str = "Unknown"
        
        # Get system load
        try:
            with open('/proc/loadavg', 'r') as f:
                load_data = f.readline().split()
                load_1min = load_data[0]
                load_5min = load_data[1]
                load_15min = load_data[2]
        except Exception:
            load_1min = load_5min = load_15min = "Unknown"
        
        # Get memory usage
        try:
            with open('/proc/meminfo', 'r') as f:
                meminfo = f.readlines()
                mem_total = int([line for line in meminfo if line.startswith('MemTotal:')][0].split()[1])
                mem_available = int([line for line in meminfo if line.startswith('MemAvailable:')][0].split()[1])
                mem_used = mem_total - mem_available
                mem_percent = (mem_used / mem_total) * 100
        except Exception:
            mem_total = mem_used = mem_percent = 0
        
        return jsonify({
            'success': True,
            'system': {
                'uptime': uptime_str,
                'uptime_seconds': uptime_seconds if 'uptime_seconds' in locals() else 0,
                'load': {
                    '1min': load_1min,
                    '5min': load_5min,
                    '15min': load_15min
                },
                'memory': {
                    'total_mb': mem_total // 1024,
                    'used_mb': mem_used // 1024,
                    'usage_percent': round(mem_percent, 1)
                },
                'timestamp': datetime.now().isoformat()
            }
        })
        
    except Exception as e:
        logger.error(f"API: Error getting system status: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to get system status: {str(e)}'
        }), 500


@bp.route('/system/info', methods=['GET'])
def system_info():
    """
    Get basic system information
    
    Returns:
        JSON response with system information
    """
    try:
        # Get hostname
        import socket
        hostname = socket.gethostname()
        
        # Get OS information
        try:
            with open('/etc/os-release', 'r') as f:
                os_release = f.readlines()
                os_name = "Unknown"
                os_version = "Unknown"
                for line in os_release:
                    if line.startswith('PRETTY_NAME='):
                        os_name = line.split('=')[1].strip().strip('"')
                    elif line.startswith('VERSION='):
                        os_version = line.split('=')[1].strip().strip('"')
        except Exception:
            os_name = "Unknown"
            os_version = "Unknown"
        
        # Get kernel version
        try:
            import platform
            kernel = platform.release()
        except Exception:
            kernel = "Unknown"
        
        return jsonify({
            'success': True,
            'system_info': {
                'hostname': hostname,
                'os_name': os_name,
                'os_version': os_version,
                'kernel': kernel,
                'python_version': platform.python_version(),
                'timestamp': datetime.now().isoformat()
            }
        })
        
    except Exception as e:
        logger.error(f"API: Error getting system info: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to get system info: {str(e)}'
        }), 500