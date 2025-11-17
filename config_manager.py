"""
PiBridge Configuration Manager

Handles YAML configuration files for networks and hotspot settings.
"""

import os
import yaml
from datetime import datetime
from pathlib import Path
from exceptions import ConfigError
from logger import setup_logger


class ConfigManager:
    """Manages PiBridge configuration files"""
    
    def __init__(self, config_dir=None):
        self.logger = setup_logger()
        self.config_dir = Path(config_dir) if config_dir else Path.home() / 'pibridge'
        self.config_dir.mkdir(exist_ok=True)
        
        # Configuration file paths
        self.networks_file = self.config_dir / 'networks.yaml'
        self.hotspot_file = self.config_dir / 'hotspot.yaml'
        self.log_file = self.config_dir / 'pibridge.log'
        
        # Ensure files exist
        self._ensure_config_files()
    
    def _ensure_config_files(self):
        """Ensure configuration files exist with defaults"""
        if not self.networks_file.exists():
            with open(self.networks_file, 'w') as f:
                yaml.dump({'networks': []}, f)
        
        if not self.hotspot_file.exists():
            default_hotspot = {
                'hotspot': {
                    'ssid': 'pibridge',
                    'password': 'pibridge123',
                    'interface': 'wlan0',
                    'ip_address': '192.168.4.1',
                    'subnet_mask': '255.255.255.0',
                    'dhcp_start': '192.168.4.10',
                    'dhcp_end': '192.168.4.50',
                    'channel': 6,
                    'country_code': 'US'
                }
            }
            with open(self.hotspot_file, 'w') as f:
                yaml.dump(default_hotspot, f)
    
    def load_networks(self):
        """Load saved networks from YAML file"""
        try:
            with open(self.networks_file, 'r') as f:
                data = yaml.safe_load(f)
                return data.get('networks', [])
        except Exception as e:
            self.logger.error(f"Failed to load networks: {e}")
            return []
    
    def save_network(self, ssid, password):
        """Save a network to the configuration"""
        try:
            networks = self.load_networks()
            
            # Check if network already exists
            existing = next((n for n in networks if n['ssid'] == ssid), None)
            if existing:
                existing['password'] = password
                existing['last_connected'] = datetime.now().isoformat()
            else:
                networks.append({
                    'ssid': ssid,
                    'password': password,
                    'added_date': datetime.now().isoformat(),
                    'last_connected': None
                })
            
            data = {'networks': networks}
            with open(self.networks_file, 'w') as f:
                yaml.dump(data, f)
            
            self.logger.info(f"Network '{ssid}' saved successfully")
            return True
        except Exception as e:
            self.logger.error(f"Failed to save network '{ssid}': {e}")
            raise ConfigError(f"Failed to save network: {e}")
    
    def remove_network(self, ssid):
        """Remove a network from configuration"""
        try:
            networks = self.load_networks()
            original_count = len(networks)
            networks = [n for n in networks if n['ssid'] != ssid]
            
            if len(networks) == original_count:
                return False  # Network not found
            
            data = {'networks': networks}
            with open(self.networks_file, 'w') as f:
                yaml.dump(data, f)
            
            self.logger.info(f"Network '{ssid}' removed successfully")
            return True
        except Exception as e:
            self.logger.error(f"Failed to remove network '{ssid}': {e}")
            raise ConfigError(f"Failed to remove network: {e}")
    
    def load_hotspot_config(self):
        """Load hotspot configuration"""
        try:
            with open(self.hotspot_file, 'r') as f:
                data = yaml.safe_load(f)
                return data.get('hotspot', {})
        except Exception as e:
            self.logger.error(f"Failed to load hotspot config: {e}")
            return {}
    
    def save_hotspot_config(self, config):
        """Save hotspot configuration"""
        try:
            data = {'hotspot': config}
            with open(self.hotspot_file, 'w') as f:
                yaml.dump(data, f)
            self.logger.info("Hotspot configuration saved successfully")
            return True
        except Exception as e:
            self.logger.error(f"Failed to save hotspot config: {e}")
            raise ConfigError(f"Failed to save hotspot config: {e}")
    
    def list_networks(self):
        """List saved networks - API compatibility method"""
        return self.load_networks()
    
    def get_profile(self, name):
        """Get a specific profile - API compatibility method for bridge management"""
        networks = self.load_networks()
        for network in networks:
            if network.get('name', network.get('ssid')) == name:
                return network
        return None
    
    def update_last_connected(self, ssid):
        """Update last_connected timestamp for a network"""
        try:
            networks = self.load_networks()
            for network in networks:
                if network['ssid'] == ssid:
                    network['last_connected'] = datetime.now().isoformat()
                    break
            
            data = {'networks': networks}
            with open(self.networks_file, 'w') as f:
                yaml.dump(data, f)
                
            self.logger.info(f"Updated last_connected for network '{ssid}'")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to update last_connected for '{ssid}': {e}")
            return False