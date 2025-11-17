"""
PiBridge rfkill Checker

Checks wireless hardware status using rfkill.
"""

import subprocess
from logger import setup_logger
from exceptions import WiFiError


class RfkillChecker:
    """Check wireless hardware status using rfkill"""
    
    def __init__(self):
        self.logger = setup_logger()
    
    def check_wifi_status(self):
        """Check WiFi hardware status"""
        try:
            cmd = ['rfkill', 'list', 'wifi']
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            lines = result.stdout.strip().split('\n')
            status = {
                'exists': False,
                'blocked': False,
                'blocked_type': None,
                'hard_blocked': False,
                'soft_blocked': False
            }
            
            for line in lines:
                if line.startswith('0:'):
                    status['exists'] = True
                    
                    if 'Soft blocked: yes' in line:
                        status['blocked'] = True
                        status['blocked_type'] = 'soft'
                        status['soft_blocked'] = True
                    elif 'Hard blocked: yes' in line:
                        status['blocked'] = True
                        status['blocked_type'] = 'hard'
                        status['hard_blocked'] = True
            
            return status
            
        except subprocess.CalledProcessError:
            return {
                'exists': False,
                'blocked': False,
                'error': 'rfkill not available'
            }
        except Exception as e:
            self.logger.error(f"Error checking rfkill status: {e}")
            return {
                'exists': False,
                'blocked': False,
                'error': str(e)
            }
    
    def is_wifi_available(self):
        """Check if WiFi is available for use"""
        status = self.check_wifi_status()
        return status['exists'] and not status['blocked']
    
    def unblock_wifi(self):
        """Unblock WiFi if it's soft-blocked"""
        try:
            status = self.check_wifi_status()
            
            if status['hard_blocked']:
                self.logger.warning("WiFi is hard-blocked (physical switch)")
                return False
            
            if status['soft_blocked']:
                cmd = ['sudo', 'rfkill', 'unblock', 'wifi']
                subprocess.run(cmd, check=True)
                self.logger.info("WiFi unblocked successfully")
                return True
            
            self.logger.info("WiFi is not blocked")
            return True
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to unblock WiFi: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error unblocking WiFi: {e}")
            return False


# Add the check_rfkill function that API modules expect
def check_rfkill():
    """Check rfkill status - wrapper function for API compatibility"""
    checker = RfkillChecker()
    status = checker.check_wifi_status()
    
    if status['hard_blocked']:
        from exceptions import RfkillBlockedException
        raise RfkillBlockedException("WiFi is hard-blocked (physical switch)")
    elif status['soft_blocked']:
        from exceptions import RfkillBlockedException
        raise RfkillBlockedException("WiFi is soft-blocked")
    
    return status