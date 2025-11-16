#!/usr/bin/env python3
"""
PySerial TCP2COM Bridge Manager for PiBridge

Provides functionality to create TCP to Serial bridges using PySerial.
"""

import os
import json
import subprocess
import time
import signal
from logger import setup_logger
from datetime import datetime


class PySerialTCP2COMManager:
    """Manages PySerial TCP2COM bridges and profiles"""
    
    def __init__(self, profiles_file="pyserial_profiles.json"):
        self.logger = setup_logger()
        self.profiles_file = profiles_file
        self.profiles = self._load_profiles()
        self.active_process = None
        
    def _load_profiles(self):
        """Load profiles from JSON file"""
        try:
            if os.path.exists(self.profiles_file):
                with open(self.profiles_file, 'r') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            self.logger.error(f"Error loading profiles: {e}")
            return {}
    
    def _save_profiles(self):
        """Save profiles to JSON file"""
        try:
            with open(self.profiles_file, 'w') as f:
                json.dump(self.profiles, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving profiles: {e}")
    
    def list_profiles(self):
        """List all available profiles"""
        return self.profiles.copy()
    
    def add_profile(self, name, device, baudrate, port, bytesize=8, parity='N', stopbits=1, timeout=1.0, description=""):
        """Add a new profile"""
        try:
            self.profiles[name] = {
                'device': device,
                'baudrate': baudrate,
                'port': port,
                'bytesize': bytesize,
                'parity': parity,
                'stopbits': stopbits,
                'timeout': timeout,
                'description': description,
                'created': datetime.now().isoformat()
            }
            self._save_profiles()
            self.logger.info(f"Added profile '{name}' for device {device}")
            return True
        except Exception as e:
            self.logger.error(f"Error adding profile '{name}': {e}")
            return False
    
    def remove_profile(self, name):
        """Remove a profile"""
        try:
            if name in self.profiles:
                del self.profiles[name]
                self._save_profiles()
                self.logger.info(f"Removed profile '{name}'")
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error removing profile '{name}': {e}")
            return False
    
    def update_profile(self, name, **kwargs):
        """Update an existing profile"""
        try:
            if name in self.profiles:
                self.profiles[name].update(kwargs)
                self._save_profiles()
                self.logger.info(f"Updated profile '{name}'")
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error updating profile '{name}': {e}")
            return False
    
    def list_serial_devices(self):
        """List available serial devices"""
        devices = []
        try:
            # Check for actual serial devices using find command
            try:
                result = subprocess.run([
                    'find', '/dev', '-name', 'ttyUSB*', '-o', '-name', 'ttyACM*'
                ], capture_output=True, text=True)
                
                if result.returncode == 0 and result.stdout.strip():
                    for device_path in result.stdout.strip().split('\n'):
                        device_path = device_path.strip()
                        if device_path:
                            devices.append({
                                'device': device_path,
                                'description': f'Serial device {os.path.basename(device_path)}',
                                'hardware_id': self._get_device_info(device_path)
                            })
            except Exception as e:
                self.logger.debug(f"Error scanning /dev for USB/ACM devices: {e}")
            
            # Add some common virtual devices for testing only if no real devices found
            if not devices:
                devices.extend([
                    {
                        'device': '/dev/pts/0',
                        'description': 'Virtual PTY device',
                        'hardware_id': 'Virtual'
                    },
                    {
                        'device': '/dev/ttyV0',
                        'description': 'Virtual serial device',
                        'hardware_id': 'Virtual'
                    }
                ])
            
            self.logger.info(f"Found {len(devices)} serial devices")
            return devices
            
        except Exception as e:
            self.logger.error(f"Error listing serial devices: {e}")
            return []
    
    def _get_device_info(self, device_path):
        """Get hardware information for a device"""
        try:
            if os.path.exists('/sys/class/tty/' + os.path.basename(device_path)):
                hardware_id_file = f'/sys/class/tty/{os.path.basename(device_path)}/device/uevent'
                if os.path.exists(hardware_id_file):
                    with open(hardware_id_file, 'r') as f:
                        for line in f:
                            if line.startswith('DRIVER='):
                                return line.split('=')[1].strip()
            return 'Unknown'
        except Exception:
            return 'Unknown'
    
    def start_bridge(self, profile_name=None):
        """Start the TCP2COM bridge"""
        try:
            if self.active_process:
                self.logger.warning("Bridge is already running")
                return False
            
            if not profile_name:
                profile_name = 'default'
            
            if profile_name not in self.profiles:
                self.logger.error(f"Profile '{profile_name}' not found")
                return False
            
            profile = self.profiles[profile_name]
            
            # Create the bridge command
            cmd = [
                'python3', '-c',
                f'''
import socket
import serial
import threading
import sys

def bridge_tcp_to_serial():
    host = "0.0.0.0"
    port = {profile['port']}
    
    try:
        # Create TCP server
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((host, port))
        server.listen(1)
        print(f"TCP server listening on {{host}}:{{port}}", flush=True)
        
        # Connect to serial device
        ser = serial.Serial(
            "{profile['device']}",
            baudrate={profile['baudrate']},
            bytesize={profile['bytesize']},
            parity="{profile['parity']}",
            stopbits={profile['stopbits']},
            timeout={profile['timeout']}
        )
        print(f"Connected to serial device {{ser.port}}", flush=True)
        
        while True:
            # Accept TCP connection
            client, addr = server.accept()
            print(f"TCP connection from {{addr}}", flush=True)
            
            def forward_tcp_to_serial():
                try:
                    while True:
                        data = client.recv(1024)
                        if not data:
                            break
                        ser.write(data)
                except Exception as e:
                    print(f"Error forwarding TCP to serial: {{e}}", flush=True)
                finally:
                    client.close()
            
            def forward_serial_to_tcp():
                try:
                    while True:
                        data = ser.read(1024)
                        if not data:
                            break
                        client.send(data)
                except Exception as e:
                    print(f"Error forwarding serial to TCP: {{e}}", flush=True)
                finally:
                    client.close()
            
            # Start bidirectional forwarding
            tcp_to_serial_thread = threading.Thread(target=forward_tcp_to_serial)
            serial_to_tcp_thread = threading.Thread(target=forward_serial_to_tcp)
            
            tcp_to_serial_thread.daemon = True
            serial_to_tcp_thread.daemon = True
            
            tcp_to_serial_thread.start()
            serial_to_tcp_thread.start()
            
    except Exception as e:
        print(f"Bridge error: {{e}}", flush=True)
        sys.exit(1)

bridge_tcp_to_serial()
                '''
            ]
            
            # Start the bridge process
            self.active_process = subprocess.Popen(cmd)
            
            # Give it a moment to start
            time.sleep(1)
            
            if self.active_process.poll() is None:
                self.logger.info(f"Bridge started successfully with profile '{profile_name}' on port {profile['port']}")
                return True
            else:
                self.logger.error("Failed to start bridge process")
                return False
                
        except Exception as e:
            self.logger.error(f"Error starting bridge: {e}")
            return False
    
    def stop_bridge(self):
        """Stop the TCP2COM bridge"""
        try:
            if self.active_process:
                self.active_process.terminate()
                self.active_process.wait(timeout=5)
                self.active_process = None
                self.logger.info("Bridge stopped successfully")
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error stopping bridge: {e}")
            if self.active_process:
                self.active_process.kill()
                self.active_process = None
            return True
    
    def restart_bridge(self, profile_name=None):
        """Restart the bridge"""
        self.stop_bridge()
        time.sleep(1)
        return self.start_bridge(profile_name)
    
    def is_active(self):
        """Check if bridge is active"""
        return self.active_process is not None and self.active_process.poll() is None
    
    def get_status(self):
        """Get current bridge status"""
        class Status:
            def __init__(self):
                self.active = self_parent.is_active() if 'self_parent' in locals() else False
                self.port = None
                self.device = None
        
        # Get active profile info if running
        if self.is_active() and hasattr(self, '_last_profile'):
            profile = self.profiles.get(self._last_profile)
            if profile:
                status = Status()
                status.active = True
                status.port = profile['port']
                status.device = profile['device']
                return status
        
        return Status()


if __name__ == '__main__':
    # Create default profile if none exists
    manager = PySerialTCP2COMManager()
    
    if not manager.list_profiles():
        # Create a default profile for testing
        manager.add_profile(
            name="default",
            device="/dev/ttyUSB0",
            baudrate=9600,
            port=8000,
            description="Default test profile"
        )
        print("Created default profile")
    
    # Test device listing
    devices = manager.list_serial_devices()
    print(f"Available devices: {devices}")