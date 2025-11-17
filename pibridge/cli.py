#!/usr/bin/env python3
"""
PiBridge Command Line Interface

Provides command-line access to PiBridge functionality including hotspot management.
"""

import sys
import argparse
import json
import requests
from pathlib import Path
import subprocess

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from hotspot import HotspotManager, HotspotStatus
    from rfkill_checker import check_rfkill
    from logger import setup_logger
    from config_manager import ConfigManager
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
    
    def check_rfkill():
        return {'exists': True, 'blocked': False}
    
    def setup_logger(*args, **kwargs): 
        return type('Logger', (), {'info': print, 'error': print, 'warning': print})()


def create_cli_logger():
    """Create logger for CLI"""
    return setup_logger(verbose=True, debug=False)


def hotspot_status():
    """Get hotspot status via CLI"""
    logger = create_cli_logger()
    logger.info("Getting hotspot status...")
    
    try:
        # Try to get status from web API first
        try:
            response = requests.get('http://localhost:5000/api/hotspot/status', timeout=5)
            if response.status_code == 200:
                data = response.json()
                hotspot = data.get('hotspot', {})
                print(f"Hotspot Status: {'Active' if hotspot.get('active') else 'Inactive'}")
                print(f"SSID: {hotspot.get('ssid')}")
                print(f"Interface: {hotspot.get('interface')}")
                print(f"IP Address: {hotspot.get('ip_address')}")
                print(f"Connected Clients: {hotspot.get('clients', 0)}")
                return True
        except:
            pass  # Fall back to direct method
        
        # Fall back to direct hotspot manager
        hotspot = HotspotManager()
        status = hotspot.get_status()
        
        print(f"Hotspot Status: {'Active' if status.active else 'Inactive'}")
        print(f"SSID: {status.ssid}")
        print(f"Interface: {status.interface}")
        print(f"IP Address: {status.ip_address}")
        print(f"Connected Clients: {status.clients}")
        return True
        
    except Exception as e:
        logger.error(f"Error getting hotspot status: {e}")
        print(f"Error: {e}")
        return False


def hotspot_start():
    """Start hotspot via CLI"""
    logger = create_cli_logger()
    logger.info("Starting hotspot...")
    
    try:
        # Check rfkill status first
        try:
            check_rfkill()
        except Exception as e:
            print(f"Error: Wireless is blocked: {e}")
            print("Please unblock it using: sudo rfkill unblock wifi")
            return False
        
        # Start hotspot via web API
        try:
            response = requests.post('http://localhost:5000/api/hotspot/start', timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    print("Hotspot started successfully!")
                    hotspot = data.get('hotspot', {})
                    print(f"SSID: {hotspot.get('ssid')}")
                    print(f"Interface: {hotspot.get('interface')}")
                    print(f"IP Address: {hotspot.get('ip_address')}")
                    return True
                else:
                    print(f"Failed to start hotspot: {data.get('error')}")
                    return False
            else:
                print(f"API Error: {response.status_code} - {response.text}")
                return False
        except requests.ConnectionError:
            print("Warning: Web API not available, trying direct method...")
        
        # Fall back to direct hotspot manager
        hotspot = HotspotManager()
        success = hotspot.start_hotspot()
        
        if success:
            print("Hotspot started successfully!")
            return True
        else:
            print("Failed to start hotspot")
            return False
            
    except Exception as e:
        logger.error(f"Error starting hotspot: {e}")
        print(f"Error: {e}")
        return False


def hotspot_stop():
    """Stop hotspot via CLI"""
    logger = create_cli_logger()
    logger.info("Stopping hotspot...")
    
    try:
        # Stop hotspot via web API
        try:
            response = requests.post('http://localhost:5000/api/hotspot/stop', timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    print("Hotspot stopped successfully!")
                    return True
                else:
                    print(f"Failed to stop hotspot: {data.get('error')}")
                    return False
            else:
                print(f"API Error: {response.status_code} - {response.text}")
                return False
        except requests.ConnectionError:
            print("Warning: Web API not available, trying direct method...")
        
        # Fall back to direct hotspot manager
        hotspot = HotspotManager()
        success = hotspot.stop_hotspot()
        
        if success:
            print("Hotspot stopped successfully!")
            return True
        else:
            print("Failed to stop hotspot")
            return False
            
    except Exception as e:
        logger.error(f"Error stopping hotspot: {e}")
        print(f"Error: {e}")
        return False


def wifi_scan():
    """Scan for WiFi networks via CLI"""
    logger = create_cli_logger()
    logger.info("Scanning for WiFi networks...")
    
    try:
        # Try to get networks from web API first
        try:
            response = requests.get('http://localhost:5000/api/networks/scan', timeout=10)
            if response.status_code == 200:
                data = response.json()
                networks = data.get('networks', [])
                print(f"Found {len(networks)} networks:")
                for network in networks:
                    print(f"  {network.get('ssid', 'Unknown')} - {network.get('signal', 'Unknown')} dBm")
                return True
        except:
            pass  # Fall back to direct method
        
        # Fall back to direct scanner
        from scanner import NetworkScanner
        scanner = NetworkScanner()
        networks = scanner.scan_networks()
        
        print(f"Found {len(networks)} networks:")
        for network in networks:
            print(f"  {network.get('ssid', 'Unknown')} - {network.get('signal', 'Unknown')} dBm")
        return True
        
    except Exception as e:
        logger.error(f"Error scanning WiFi networks: {e}")
        print(f"Error: {e}")
        return False


def status():
    """Show overall system status"""
    logger = create_cli_logger()
    logger.info("Getting system status...")
    
    try:
        print("PiBridge System Status")
        print("=====================")
        
        # Check rfkill status
        try:
            rfkill_status = check_rfkill()
            print(f"WiFi Hardware: {'Available' if rfkill_status.get('exists') and not rfkill_status.get('blocked') else 'Blocked'}")
            if rfkill_status.get('blocked'):
                print(f"  Blocked: {rfkill_status.get('blocked_type', 'unknown')}")
        except Exception as e:
            print(f"WiFi Hardware: Error checking - {e}")
        
        # Check hotspot status
        try:
            hotspot = HotspotManager()
            status = hotspot.get_status()
            print(f"Hotspot: {'Active' if status.active else 'Inactive'}")
            if status.active:
                print(f"  SSID: {status.ssid}")
                print(f"  Interface: {status.interface}")
                print(f"  Clients: {status.clients}")
        except Exception as e:
            print(f"Hotspot: Error checking - {e}")
        
        # Check web service
        try:
            response = requests.get('http://localhost:5000/api/status', timeout=2)
            print(f"Web Service: {'Running' if response.status_code == 200 else 'Not Available'}")
        except:
            print("Web Service: Not Available")
        
        return True
        
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        print(f"Error: {e}")
        return False


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='PiBridge - WiFi management tool for Raspberry Pi',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  pibridge status              # Show overall system status
  pibridge hotspot status      # Get hotspot status
  pibridge hotspot start       # Start WiFi hotspot
  pibridge hotspot stop        # Stop WiFi hotspot
  pibridge wifi scan           # Scan for WiFi networks
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Status command
    status_parser = subparsers.add_parser('status', help='Show system status')
    
    # Hotspot commands
    hotspot_parser = subparsers.add_parser('hotspot', help='Hotspot management')
    hotspot_subparsers = hotspot_parser.add_subparsers(dest='hotspot_action')
    
    hotspot_status_parser = hotspot_subparsers.add_parser('status', help='Get hotspot status')
    hotspot_start_parser = hotspot_subparsers.add_parser('start', help='Start WiFi hotspot')
    hotspot_stop_parser = hotspot_subparsers.add_parser('stop', help='Stop WiFi hotspot')
    
    # WiFi commands
    wifi_parser = subparsers.add_parser('wifi', help='WiFi network management')
    wifi_subparsers = wifi_parser.add_subparsers(dest='wifi_action')
    
    wifi_scan_parser = wifi_subparsers.add_parser('scan', help='Scan for WiFi networks')
    
    # Parse arguments
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Execute appropriate command
    success = False
    
    if args.command == 'status':
        success = status()
    elif args.command == 'hotspot':
        if args.hotspot_action == 'status':
            success = hotspot_status()
        elif args.hotspot_action == 'start':
            success = hotspot_start()
        elif args.hotspot_action == 'stop':
            success = hotspot_stop()
        else:
            hotspot_parser.print_help()
    elif args.command == 'wifi':
        if args.wifi_action == 'scan':
            success = wifi_scan()
        else:
            wifi_parser.print_help()
    else:
        parser.print_help()
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())