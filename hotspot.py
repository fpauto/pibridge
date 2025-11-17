"""
PiBridge Hotspot Manager

Manages WiFi hotspot functionality using hostapd and dnsmasq.
"""

import subprocess
import os
import time
import signal
from pathlib import Path
from config_manager import ConfigManager
from logger import setup_logger
from exceptions import HotspotError


class HotspotManager:
    """Manages WiFi hotspot operations"""
    
    def __init__(self):
        self.logger = setup_logger()
        self.config_manager = ConfigManager()
        self.interface = 'wlan0'
        self.hotspot_config = {}
        self.hostapd_process = None
        self.dnsmasq_process = None
        
        # Load hotspot configuration
        self._load_config()
    
    def _load_config(self):
        """Load hotspot configuration"""
        try:
            self.hotspot_config = self.config_manager.load_hotspot_config()
            self.logger.info("Hotspot configuration loaded")
        except Exception as e:
            self.logger.error(f"Failed to load hotspot config: {e}")
            # Use defaults
            self.hotspot_config = {
                'ssid': 'pibridge',
                'password': 'pibridge123',
                'interface': 'wlan0',
                'ip_address': '192.168.4.1',
                'dhcp_start': '192.168.4.10',
                'dhcp_end': '192.168.4.50',
                'channel': 6,
                'country_code': 'US'
            }
    
    def is_hotspot_active(self):
        """Check if hotspot is currently running"""
        try:
            # Check if hostapd is running
            cmd = ['pgrep', '-f', 'hostapd']
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                # Check if interface has hotspot IP
                cmd = ['ip', 'addr', 'show', self.interface]
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                
                if self.hotspot_config.get('ip_address') in result.stdout:
                    return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error checking hotspot status: {e}")
            return False
    
    def start_hotspot(self):
        """Start WiFi hotspot"""
        try:
            self.logger.info("=== Starting WiFi Hotspot Process ===")
            if self.is_hotspot_active():
                self.logger.info("Hotspot is already running")
                return True
            
            # Check if we have the required sudo privileges
            if not self._check_sudo_access():
                error_msg = "Hotspot functionality requires sudo privileges. Please run the web interface as root or with appropriate permissions."
                self.logger.error(f"Access check failed: {error_msg}")
                raise HotspotError(error_msg)
            
            self.logger.info("✓ Sudo access verified")
            
            # Disconnect any current WiFi connection
            self.logger.info("Step 1/6: Disconnecting WiFi...")
            self._disconnect_wifi()
            
            # Configure interface IP
            self.logger.info("Step 2/6: Configuring interface IP...")
            self._configure_interface_ip()
            
            # Create configuration files
            self.logger.info("Step 3/6: Creating configuration files...")
            self._create_hostapd_config()
            self._create_dnsmasq_config()
            
            # Start hostapd
            self.logger.info("Step 4/6: Starting hostapd...")
            self._start_hostapd()
            
            # Start dnsmasq
            self.logger.info("Step 5/6: Starting dnsmasq...")
            self._start_dnsmasq()
            
            # Wait a moment for services to start
            self.logger.info("Step 6/6: Verifying startup...")
            time.sleep(3)
            
            if self.is_hotspot_active():
                self.logger.info("✓ Hotspot started successfully")
                self.logger.info(f"  SSID: {self.hotspot_config.get('ssid')}")
                self.logger.info(f"  Interface: {self.interface}")
                self.logger.info(f"  IP Address: {self.hotspot_config.get('ip_address')}")
                return True
            else:
                error_msg = "Hotspot failed to start properly - verification failed"
                self.logger.error(f"✗ {error_msg}")
                raise HotspotError(error_msg)
                
        except Exception as e:
            self.logger.error(f"✗ Failed to start hotspot: {e}")
            self.logger.info("Cleaning up failed startup...")
            self.stop_hotspot()  # Clean up on failure
            raise HotspotError(f"Failed to start hotspot: {e}")
    
    def stop_hotspot(self):
        """Stop WiFi hotspot"""
        try:
            self.logger.info("Stopping WiFi hotspot...")
            
            # Stop hostapd
            if self.hostapd_process:
                self.hostapd_process.terminate()
                try:
                    self.hostapd_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.hostapd_process.kill()
                self.hostapd_process = None
            
            # Stop dnsmasq
            if self.dnsmasq_process:
                self.dnsmasq_process.terminate()
                try:
                    self.dnsmasq_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.dnsmasq_process.kill()
                self.dnsmasq_process = None
            
            # Kill any remaining processes
            subprocess.run(['pkill', '-f', 'hostapd'], capture_output=True)
            subprocess.run(['pkill', '-f', 'dnsmasq'], capture_output=True)
            
            # Remove configuration files
            self._cleanup_config_files()
            
            self.logger.info("Hotspot stopped successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error stopping hotspot: {e}")
            return False
    
    def _disconnect_wifi(self):
        """Disconnect WiFi to free interface"""
        try:
            sudo_available = self._check_sudo_access()
            cmd_prefix = ['sudo'] if sudo_available else []
            cmd = cmd_prefix + ['nmcli', 'dev', 'disconnect', self.interface]
            subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            self.logger.info("WiFi disconnected to free interface")
        except subprocess.TimeoutExpired:
            self.logger.warning("WiFi disconnect timeout")
        except Exception as e:
            self.logger.warning(f"Error disconnecting WiFi: {e}")
    
    def _configure_interface_ip(self):
        """Configure static IP on wireless interface"""
        try:
            sudo_available = self._check_sudo_access()
            if not sudo_available:
                error_msg = "Hotspot startup requires sudo privileges. Please run with sudo or as root."
                self.logger.error(f"✗ {error_msg}")
                raise HotspotError(error_msg)
            
            cmd_prefix = ['sudo'] if sudo_available else []
            
            # Check if interface exists
            result = subprocess.run(['ip', 'link', 'show', self.interface],
                                 capture_output=True, text=True)
            if result.returncode != 0:
                error_msg = f"Wireless interface {self.interface} not found"
                self.logger.error(f"✗ {error_msg}")
                raise HotspotError(error_msg)
            
            self.logger.info(f"✓ Interface {self.interface} found")
            
            # Remove any existing IP configuration
            cmd = cmd_prefix + ['ip', 'addr', 'flush', 'dev', self.interface]
            self.logger.info(f"Executing: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                self.logger.warning(f"IP flush warning: {result.stderr}")
            
            # Add static IP
            ip = self.hotspot_config.get('ip_address', '192.168.4.1')
            cmd = cmd_prefix + ['ip', 'addr', 'add', f'{ip}/24', 'dev', self.interface]
            self.logger.info(f"Executing: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                error_msg = f"Failed to add IP address: {result.stderr}"
                self.logger.error(f"✗ {error_msg}")
                raise HotspotError(error_msg)
            
            # Bring interface up
            cmd = cmd_prefix + ['ip', 'link', 'set', self.interface, 'up']
            self.logger.info(f"Executing: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                error_msg = f"Failed to bring interface up: {result.stderr}"
                self.logger.error(f"✗ {error_msg}")
                raise HotspotError(error_msg)
            
            # Verify configuration
            result = subprocess.run(['ip', 'addr', 'show', self.interface],
                                 capture_output=True, text=True)
            if ip in result.stdout:
                self.logger.info(f"✓ Interface {self.interface} configured with IP {ip}")
            else:
                raise HotspotError(f"Interface configuration verification failed for IP {ip}")
            
        except subprocess.CalledProcessError as e:
            error_msg = str(e).strip()
            self.logger.error(f"✗ Failed to configure interface IP: {error_msg}")
            
            # Check if it's a permission issue
            if "Operation not permitted" in error_msg or "Permission denied" in error_msg:
                raise HotspotError("Permission denied. Hotspot requires sudo privileges to configure network interfaces.")
            else:
                raise HotspotError(f"Failed to configure interface: {error_msg}")
    
    def _check_sudo_access(self):
        """Check if we have sudo access"""
        try:
            result = subprocess.run(['sudo', '-n', 'true'],
                                   capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except:
            return False
    
    def _create_hostapd_config(self):
        """Create hostapd configuration file"""
        try:
            config_path = '/tmp/pibridge_hostapd.conf'
            
            config_content = f"""# PiBridge Hotspot Configuration
interface={self.interface}
driver=nl80211
ssid={self.hotspot_config.get('ssid', 'pibridge')}
hw_mode=g
channel={self.hotspot_config.get('channel', 6)}
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase={self.hotspot_config.get('password', 'pibridge123')}
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
country_code={self.hotspot_config.get('country_code', 'US')}
"""
            
            with open(config_path, 'w') as f:
                f.write(config_content)
            
            self.logger.info(f"Created hostapd config at {config_path}")
            
        except Exception as e:
            self.logger.error(f"Failed to create hostapd config: {e}")
            raise HotspotError(f"Failed to create hostapd config: {e}")
    
    def _create_dnsmasq_config(self):
        """Create dnsmasq configuration file"""
        try:
            config_path = '/tmp/pibridge_dnsmasq.conf'
            
            config_content = f"""# PiBridge DHCP Configuration
interface={self.interface}
dhcp-range={self.hotspot_config.get('dhcp_start', '192.168.4.10')},{self.hotspot_config.get('dhcp_end', '192.168.4.50')},255.255.255.0,12h
dhcp-option=3,{self.hotspot_config.get('ip_address', '192.168.4.1')}
dhcp-option=6,{self.hotspot_config.get('ip_address', '192.168.4.1')}
server=8.8.8.8
log-queries
log-dhcp
"""
            
            with open(config_path, 'w') as f:
                f.write(config_content)
            
            self.logger.info(f"Created dnsmasq config at {config_path}")
            
        except Exception as e:
            self.logger.error(f"Failed to create dnsmasq config: {e}")
            raise HotspotError(f"Failed to create dnsmasq config: {e}")
    
    def _start_hostapd(self):
        """Start hostapd daemon"""
        try:
            config_path = '/tmp/pibridge_hostapd.conf'
            sudo_available = self._check_sudo_access()
            cmd_prefix = ['sudo'] if sudo_available else []
            cmd = cmd_prefix + ['hostapd', '-B', '-f', '/tmp/hostapd.log', config_path]
            
            self.logger.info(f"Executing: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            # Verify hostapd is actually running
            time.sleep(1)
            check_result = subprocess.run(['pgrep', '-f', 'hostapd'], capture_output=True)
            if check_result.returncode != 0:
                raise HotspotError("hostapd process not found after startup command")
            
            pid = check_result.stdout.decode('utf-8', errors='replace').strip().split('\n')[0] if check_result.stdout.strip() else 'unknown'
            self.logger.info(f"✓ hostapd started successfully (PID: {pid})")
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"✗ Failed to start hostapd (return code: {e.returncode})")
            stderr_text = e.stderr.decode('utf-8', errors='replace').strip() if hasattr(e, 'stderr') and e.stderr else ''
            stdout_text = e.stdout.decode('utf-8', errors='replace').strip() if hasattr(e, 'stdout') and e.stdout else ''
            if stderr_text:
                self.logger.error(f"stderr: {stderr_text}")
            if stdout_text:
                self.logger.error(f"stdout: {stdout_text}")
            raise HotspotError(f"Failed to start hostapd: {e}")
    
    def _start_dnsmasq(self):
        """Start dnsmasq daemon"""
        try:
            config_path = '/tmp/pibridge_dnsmasq.conf'
            sudo_available = self._check_sudo_access()
            cmd_prefix = ['sudo'] if sudo_available else []
            cmd = cmd_prefix + ['dnsmasq', '-C', config_path]
            
            self.logger.info(f"Executing: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            # Verify dnsmasq is actually running
            time.sleep(1)
            check_result = subprocess.run(['pgrep', '-f', 'dnsmasq'], capture_output=True)
            if check_result.returncode != 0:
                raise HotspotError("dnsmasq process not found after startup command")
            
            pid = check_result.stdout.decode('utf-8', errors='replace').strip().split('\n')[0] if check_result.stdout.strip() else 'unknown'
            self.logger.info(f"✓ dnsmasq started successfully (PID: {pid})")
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"✗ Failed to start dnsmasq (return code: {e.returncode})")
            stderr_text = e.stderr.decode('utf-8', errors='replace').strip() if hasattr(e, 'stderr') and e.stderr else ''
            stdout_text = e.stdout.decode('utf-8', errors='replace').strip() if hasattr(e, 'stdout') and e.stdout else ''
            if stderr_text:
                self.logger.error(f"stderr: {stderr_text}")
            if stdout_text:
                self.logger.error(f"stdout: {stdout_text}")
            raise HotspotError(f"Failed to start dnsmasq: {e}")
    
    def _cleanup_config_files(self):
        """Remove temporary configuration files"""
        try:
            files = [
                '/tmp/pibridge_hostapd.conf',
                '/tmp/pibridge_dnsmasq.conf',
                '/tmp/hostapd.log'
            ]
            for file_path in files:
                if os.path.exists(file_path):
                    os.remove(file_path)
            self.logger.info("Configuration files cleaned up")
        except Exception as e:
            self.logger.warning(f"Error cleaning up config files: {e}")
    
    def get_hotspot_info(self):
        """Get current hotspot information"""
        try:
            if not self.is_hotspot_active():
                return {
                    'active': False,
                    'ssid': self.hotspot_config.get('ssid'),
                    'interface': self.interface,
                    'ip_address': self.hotspot_config.get('ip_address')
                }
            
            # Get connected clients count
            try:
                result = subprocess.run(['arp', '-an'], capture_output=True, text=True, check=True)
                clients_count = len([line for line in result.stdout.split('\n') 
                                   if self.hotspot_config.get('ip_address', '192.168.4.') in line])
            except:
                clients_count = 0
            
            return {
                'active': True,
                'ssid': self.hotspot_config.get('ssid'),
                'interface': self.interface,
                'ip_address': self.hotspot_config.get('ip_address'),
                'channel': self.hotspot_config.get('channel'),
                'clients_count': clients_count
            }
            
        except Exception as e:
            self.logger.error(f"Error getting hotspot info: {e}")
            return {'active': False, 'error': str(e)}
    
    def get_status(self):
        """Get hotspot status - API compatibility method"""
        info = self.get_hotspot_info()
        return HotspotStatus(
            active=info.get('active', False),
            ssid=info.get('ssid', 'pibridge'),
            interface=info.get('interface', 'wlan0'),
            ip_address=info.get('ip_address', '192.168.4.1'),
            clients=info.get('clients_count', 0)
        )
    
    def get_connected_clients(self):
        """Get list of connected clients"""
        try:
            # Try to get client information from dnsmasq leases
            import subprocess
            clients = []
            
            # Check for dnsmasq.leases file
            lease_files = [
                '/var/lib/misc/dnsmasq.leases',
                '/tmp/dnsmasq.leases',
                '/var/run/dnsmasq/dnsmasq.leases'
            ]
            
            for lease_file in lease_files:
                try:
                    result = subprocess.run(
                        ['sudo', 'cat', lease_file],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    
                    if result.returncode == 0:
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
                                    'connected_since': self._format_timestamp(int(timestamp)) if timestamp.isdigit() else 'unknown'
                                })
                        break  # Found lease file, stop looking
                except:
                    continue
            
            return clients
            
        except Exception as e:
            self.logger.warning(f"Could not get connected clients: {e}")
            return []
    
    def _format_timestamp(self, timestamp):
        """Format timestamp for display"""
        import datetime
        try:
            return datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
        except:
            return 'unknown'
    
    def get_interface(self):
        """Get interface name - API compatibility method"""
        return self.interface


# Additional classes and functions expected by API modules
class HotspotStatus:
    """Hotspot status data class"""
    def __init__(self, active=False, ssid="pibridge", interface="wlan0", ip_address="192.168.4.1", clients=0):
        self.active = active
        self.ssid = ssid
        self.interface = interface
        self.ip_address = ip_address
        self.clients = clients


def check_rfkill():
    """Check rfkill status - expected by API modules"""
    from rfkill_checker import RfkillChecker
    checker = RfkillChecker()
    return checker.check_wifi_status()


class RfkillBlockedException(Exception):
    """Exception for rfkill blocked state"""
    pass