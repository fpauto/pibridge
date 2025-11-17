"""
PiBridge Exceptions

Custom exceptions for PiBridge operations.
"""


class PiBridgeError(Exception):
    """Base exception for PiBridge operations"""
    pass


class WiFiError(PiBridgeError):
    """WiFi-related operations error"""
    pass


class HotspotError(PiBridgeError):
    """Hotspot operations error"""
    pass


class ConfigError(PiBridgeError):
    """Configuration operations error"""
    pass


class SerialError(PiBridgeError):
    """Serial/TCP bridge operations error"""
    pass


class NoInterfaceException(PiBridgeError):
    """No wireless interface found"""
    pass


class RfkillBlockedException(PiBridgeError):
    """Wireless is blocked by rfkill"""
    pass


class ConnectionFailedException(PiBridgeError):
    """WiFi connection failed"""
    pass


class NoSavedNetworksException(PiBridgeError):
    """No saved networks found"""
    pass