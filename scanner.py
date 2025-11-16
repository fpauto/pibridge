"""
PiBridge WiFi Scanner

Scans for available WiFi networks using nmcli.
"""

import subprocess
import re
from logger import setup_logger
from exceptions import WiFiError


class WiFiScanner:
    """WiFi network scanner using nmcli"""
    
    def __init__(self):
        self.logger = setup_logger()
        self.interface = 'wlan0'  # Default interface
    
    def scan_networks(self):
        """Scan for available WiFi networks"""
        try:
            self.logger.info("Scanning for available networks...")
            
            # Use nmcli to scan for networks
            cmd = ['nmcli', '-t', '-f', 'SSID,SIGNAL,SECURITY,FREQ,IN-USE', 'dev', 'wifi', 'list', 'ifname', self.interface]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            networks = []
            for line in result.stdout.strip().split('\n'):
                if not line.strip():
                    continue
                
                parts = line.split(':')
                if len(parts) >= 5:
                    ssid = parts[0]
                    signal = parts[1]
                    security = parts[2]
                    frequency = parts[3]
                    in_use = parts[4]
                    
                    # Skip empty SSIDs
                    if not ssid or ssid == '--':
                        continue
                    
                    # Determine signal quality
                    signal_strength = self._get_signal_quality(signal)
                    networks.append({
                        'ssid': ssid,
                        'signal': signal,
                        'signal_quality': signal_strength,
                        'security': security if security != '--' else 'Open',
                        'frequency': frequency,
                        'in_use': in_use == '*',
                        'saved': False  # Will be checked by connector
                    })
            
            self.logger.info(f"Found {len(networks)} networks")
            return networks
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"nmcli scan failed: {e}")
            raise WiFiError(f"Failed to scan networks: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error during scan: {e}")
            raise WiFiError(f"Scan failed: {e}")
    
    def scan(self):
        """Scan for available WiFi networks (API compatibility method)"""
        try:
            self.logger.info("Scanning for available networks...")
            
            # Use nmcli to scan for networks
            cmd = ['nmcli', '-t', '-f', 'SSID,SIGNAL,SECURITY,FREQ,IN-USE', 'dev', 'wifi', 'list', 'ifname', self.interface]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            networks = []
            for line in result.stdout.strip().split('\n'):
                if not line.strip():
                    continue
                
                parts = line.split(':')
                if len(parts) >= 5:
                    ssid = parts[0]
                    signal = parts[1]
                    security = parts[2]
                    frequency = parts[3]
                    in_use = parts[4]
                    
                    # Skip empty SSIDs
                    if not ssid or ssid == '--':
                        continue
                    
                    # Determine signal quality
                    signal_strength = self._get_signal_quality(signal)
                    
                    # Create WiFiNetwork objects for API compatibility
                    wifi_network = WiFiNetwork(
                        ssid=ssid,
                        signal=signal,
                        security=security if security != '--' else 'Open',
                        frequency=frequency,
                        in_use=in_use == '*',
                        saved=False  # Will be checked by connector
                    )
                    networks.append(wifi_network)
            
            self.logger.info(f"Found {len(networks)} networks")
            return networks
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"nmcli scan failed: {e}")
            raise WiFiError(f"Failed to scan networks: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error during scan: {e}")
            raise WiFiError(f"Scan failed: {e}")
    
    def _get_signal_quality(self, signal_str):
        """Convert signal strength to quality description"""
        try:
            signal = int(signal_str)
            if signal >= -30:
                return "excellent"
            elif signal >= -40:
                return "good"
            elif signal >= -50:
                return "good"
            elif signal >= -60:
                return "fair"
            elif signal >= -70:
                return "fair"
            elif signal >= -80:
                return "weak"
            else:
                return "weak"
        except (ValueError, TypeError):
            return "weak"
    
    def get_current_connection(self):
        """Get currently connected network info"""
        try:
            cmd = ['nmcli', '-t', '-f', 'ACTIVE,SSID', 'dev', 'wifi']
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            for line in result.stdout.strip().split('\n'):
                parts = line.split(':')
                if len(parts) >= 2 and parts[0] == 'yes':
                    return parts[1] if parts[1] != '--' else None
            
            return None
        except subprocess.CalledProcessError:
            return None
        except Exception:
            return None


# Additional classes and functions expected by API modules
class WiFiNetwork:
    """WiFi network data class"""
    def __init__(self, ssid, signal, security, frequency, in_use=False, saved=False):
        self.ssid = ssid
        self.signal = signal
        self.security = security
        self.frequency = frequency
        self.in_use = in_use
        self.saved = saved
        self.signal_quality = self._get_signal_quality(signal)
    
    def _get_signal_quality(self, signal_str):
        """Convert signal strength to quality description"""
        try:
            signal = int(signal_str)
            if signal >= -30:
                return "excellent"
            elif signal >= -40:
                return "good"
            elif signal >= -50:
                return "good"
            elif signal >= -60:
                return "fair"
            elif signal >= -70:
                return "fair"
            elif signal >= -80:
                return "weak"
            else:
                return "weak"
        except (ValueError, TypeError):
            return "weak"


def check_rfkill():
    """Check rfkill status - expected by API modules"""
    checker = RfkillChecker()
    return checker.check_wifi_status()