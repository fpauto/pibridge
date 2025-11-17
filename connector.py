"""
PiBridge WiFi Connector

Connects to WiFi networks using NetworkManager.
"""

import subprocess
from config_manager import ConfigManager
from scanner import WiFiScanner
from logger import setup_logger
from exceptions import WiFiError


class WiFiConnector:
    """WiFi network connector using NetworkManager"""
    
    def __init__(self):
        self.logger = setup_logger()
        self.config_manager = ConfigManager()
        self.scanner = WiFiScanner()
        self.interface = 'wlan0'
    
    def connect_to_network(self, ssid, password=None):
        """Connect to a WiFi network"""
        try:
            self.logger.info(f"Connecting to network: {ssid}")
            
            # Check if password is needed
            if not password:
                # Try to get saved password
                networks = self.config_manager.load_networks()
                network_config = next((n for n in networks if n['ssid'] == ssid), None)
                if network_config:
                    password = network_config['password']
                else:
                    raise WiFiError(f"Password required for network: {ssid}")
            
            # First, disconnect any current connection
            self.disconnect()
            
            # Create connection
            cmd = [
                'nmcli', 'dev', 'wifi', 'connect', ssid,
                'password', password,
                'ifname', self.interface,
                'name', f'pibridge-{ssid}'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            # Save the network credentials
            self.config_manager.save_network(ssid, password)
            
            self.logger.info(f"Successfully connected to {ssid}")
            return True
            
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else str(e)
            self.logger.error(f"Connection to {ssid} failed: {error_msg}")
            raise WiFiError(f"Failed to connect to {ssid}: {error_msg}")
        except Exception as e:
            self.logger.error(f"Unexpected error connecting to {ssid}: {e}")
            raise WiFiError(f"Connection failed: {e}")
    
    def auto_connect(self):
        """Auto-connect to the strongest saved network"""
        try:
            self.logger.info("Attempting auto-connect to saved networks...")
            
            # Get saved networks
            saved_networks = self.config_manager.load_networks()
            if not saved_networks:
                raise WiFiError("No saved networks found")
            
            # Scan for available networks
            available_networks = self.scanner.scan_networks()
            
            # Find saved networks that are available
            saved_available = []
            for network in available_networks:
                for saved in saved_networks:
                    if network['ssid'] == saved['ssid']:
                        network['password'] = saved['password']
                        saved_available.append(network)
                        break
            
            if not saved_available:
                raise WiFiError("No saved networks are currently available")
            
            # Sort by signal strength
            saved_available.sort(key=lambda x: int(x['signal']), reverse=True)
            
            # Try to connect to the strongest network
            for network in saved_available:
                try:
                    self.logger.info(f"Trying to connect to {network['ssid']} (signal: {network['signal']})")
                    return self.connect_to_network(network['ssid'], network['password'])
                except WiFiError as e:
                    self.logger.warning(f"Failed to connect to {network['ssid']}: {e}")
                    continue
            
            raise WiFiError("Failed to connect to any saved network")
            
        except WiFiError:
            raise
        except Exception as e:
            self.logger.error(f"Auto-connect failed: {e}")
            raise WiFiError(f"Auto-connect failed: {e}")
    
    def disconnect(self):
        """Disconnect from current WiFi network"""
        try:
            cmd = ['nmcli', 'dev', 'disconnect', self.interface]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                self.logger.info("Disconnected successfully")
                return True
            else:
                self.logger.warning(f"Disconnect command returned: {result.stderr}")
                return True  # Consider disconnection successful even if no active connection
                
        except Exception as e:
            self.logger.warning(f"Error during disconnect: {e}")
            return True  # Don't fail on disconnect errors
    
    def get_connection_status(self):
        """Get current connection status"""
        try:
            # Check if interface is connected
            cmd = ['nmcli', '-t', '-f', 'GENERAL.STATE,GENERAL.CONNECTION', 'dev', 'show', self.interface]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            lines = result.stdout.strip().split('\n')
            if len(lines) >= 2:
                state = lines[0].split(':')[1] if ':' in lines[0] else ''
                connection = lines[1].split(':')[1] if ':' in lines[1] else ''
                
                if state == 'connected' and connection:
                    return {
                        'connected': True,
                        'ssid': connection,
                        'state': state
                    }
            
            return {'connected': False, 'state': state if 'state' in locals() else 'disconnected'}
            
        except Exception as e:
            self.logger.error(f"Error getting connection status: {e}")
            return {'connected': False, 'state': 'error', 'error': str(e)}
    
    def is_wireless_blocked(self):
        """Check if wireless is blocked by rfkill"""
        try:
            cmd = ['rfkill', 'list', 'wifi']
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            # Check for soft or hard block
            if 'Soft blocked: yes' in result.stdout:
                return 'soft'
            elif 'Hard blocked: yes' in result.stdout:
                return 'hard'
            else:
                return None
                
        except subprocess.CalledProcessError:
            return None
        except Exception:
            return None
    
    def unblock_wireless(self):
        """Unblock wireless if it's soft-blocked"""
        try:
            blocked_type = self.is_wireless_blocked()
            if blocked_type == 'soft':
                cmd = ['sudo', 'rfkill', 'unblock', 'wifi']
                subprocess.run(cmd, check=True)
                self.logger.info("Wireless unblocked successfully")
                return True
            elif blocked_type == 'hard':
                self.logger.warning("Wireless is hard-blocked (physical switch)")
                return False
            else:
                self.logger.info("Wireless is not blocked")
                return True
                
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to unblock wireless: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error unblocking wireless: {e}")
            return False
    
    # API compatibility methods
    def connect(self, ssid, password):
        """Connect to a network - API compatibility method"""
        return self.connect_to_network(ssid, password)
    
    def auto_connect(self, networks=None):
        """Auto-connect to saved networks - API compatibility method"""
        if networks:
            # If networks are provided, use them (though current implementation doesn't use this parameter)
            pass
        return self.auto_connect()
    
    def get_current_connection(self):
        """Get currently connected network - API compatibility method"""
        status = self.get_connection_status()
        return status.get('ssid') if status.get('connected') else None
    
    def is_interface_available_for_hotspot(self):
        """Check if interface is available for hotspot use"""
        try:
            # Check if wireless is blocked
            if self.is_wireless_blocked():
                return False, "Wireless interface is blocked"
            
            # Check if currently connected (would need to disconnect)
            status = self.get_connection_status()
            if status.get('connected'):
                return False, "Interface is currently in use for WiFi connection"
            
            # Interface should be available
            return True, "Interface available for hotspot"
            
        except Exception as e:
            return False, f"Error checking interface availability: {e}"