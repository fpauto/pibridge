#!/usr/bin/env python3
"""
PiBridge Web Interface - Flask Application

A minimal browser-based UI for PiBridge WiFi management tool.
Provides basic controls for WiFi operations while leveraging the existing CLI backend.
"""

import os
import sys
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS

# Add parent directory to path to import pibridge modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import PiBridge modules (modules are now at root level)
try:
    from scanner import WiFiScanner
    from connector import WiFiConnector
    from config_manager import ConfigManager
    from hotspot import HotspotManager
    from logger import setup_logger
except ImportError as e:
    print(f"Warning: Could not import PiBridge modules: {e}")
    print("Make sure PiBridge is properly installed")
    # Continue anyway for development

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'pibridge-web-ui-secret-key'

# Enable CORS for development (remove in production)
CORS(app)

# Initialize logger (with fallback if import fails)
try:
    from logger import setup_logger
    logger = setup_logger(verbose=False, debug=False)
except ImportError:
    # Fallback logger for development
    import logging
    logger = logging.getLogger('pibridge-web')
    logger.addHandler(logging.StreamHandler())
    logger.setLevel(logging.INFO)
    logger.info("Using fallback logger - PiBridge modules not available")

# API endpoint imports
from pibridge_web.api import networks, connection, hotspot, service, status, bridge


@app.route('/')
def index():
    """Main page of the web interface"""
    try:
        return render_template('index.html')
    except Exception as e:
        logger.error(f"Error rendering main page: {e}")
        return f"<h1>PiBridge Web UI Error</h1><p>Error: {e}</p>"


@app.route('/api/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "PiBridge Web UI",
        "version": "1.3.0"
    })


# Register API blueprints
app.register_blueprint(networks.bp, url_prefix='/api')
app.register_blueprint(connection.bp, url_prefix='/api')
app.register_blueprint(hotspot.bp, url_prefix='/api')
app.register_blueprint(service.bp, url_prefix='/api')
app.register_blueprint(status.bp, url_prefix='/api')
app.register_blueprint(bridge.bp, url_prefix='/api/bridge')


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({"error": "Endpoint not found"}), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    logger.error(f"Internal server error: {error}")
    return jsonify({"error": "Internal server error"}), 500


if __name__ == '__main__':
    # Get configuration from environment
    host = os.environ.get('PIBRIDGE_WEB_HOST', '0.0.0.0')
    port = int(os.environ.get('PIBRIDGE_WEB_PORT', 5000))
    debug = os.environ.get('PIBRIDGE_WEB_DEBUG', 'False').lower() == 'true'
    
    logger.info(f"Starting PiBridge Web UI on {host}:{port}")
    
    # Run the Flask application
    app.run(
        host=host,
        port=port,
        debug=debug,
        threaded=True
    )