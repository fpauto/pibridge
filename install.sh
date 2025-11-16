#!/bin/bash
# PiBridge Installation Script
# Installs and configures PiBridge WiFi Management System

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PIBRIDGE_DIR="/home/fredde/pibridge"
SERVICE_USER="root"
WEB_PORT=5000

echo -e "${BLUE}=== PiBridge Installation Script ===${NC}"

# Function to print status
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_error "This script must be run as root"
        exit 1
    fi
}

# Install system dependencies
install_dependencies() {
    print_status "Installing system dependencies..."
    
    # Update package list
    apt update
    
    # Install required packages
    apt install -y \
        python3 \
        python3-pip \
        python3-venv \
        network-manager \
        wireless-tools \
        hostapd \
        dnsmasq \
        iptables \
        curl \
        wget \
        git
        
    print_status "System dependencies installed"
}

# Install Python dependencies
install_python_deps() {
    print_status "Installing Python dependencies..."
    
    # Install Flask and other web dependencies
    pip3 install flask flask-cors psutil pyserial
    
    print_status "Python dependencies installed"
}

# Setup PiBridge directory structure
setup_directories() {
    print_status "Setting up PiBridge directories..."
    
    # Create main directory if it doesn't exist
    mkdir -p $PIBRIDGE_DIR
    
    # Create subdirectories
    mkdir -p $PIBRIDGE_DIR/pibridge
    mkdir -p $PIBRIDGE_DIR/pibridge_web
    mkdir -p $PIBRIDGE_DIR/pibridge_web/api
    mkdir -p $PIBRIDGE_DIR/pibridge_web/templates
    mkdir -p $PIBRIDGE_DIR/pibridge_web/static
    
    print_status "Directory structure created"
}

# Install PiBridge core files
install_pibridge_files() {
    print_status "Installing PiBridge core files..."
    
    # Copy core Python modules
    cp pibridge/*.py $PIBRIDGE_DIR/pibridge/
    
    # Copy web interface files
    cp -r pibridge_web/* $PIBRIDGE_DIR/pibridge_web/
    
    # Copy configuration files
    cp *.yaml $PIBRIDGE_DIR/
    cp pibridge-cli $PIBRIDGE_DIR/
    
    # Make CLI executable
    chmod +x $PIBRIDGE_DIR/pibridge-cli
    
    print_status "Core files installed"
}

# Setup systemd services
setup_services() {
    print_status "Setting up systemd services..."
    
    # Web interface service
    cat > /etc/systemd/system/pibridge-web.service << EOF
[Unit]
Description=PiBridge Web UI
After=network.target
Wants=network.target

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$PIBRIDGE_DIR
ExecStart=/usr/bin/python3 $PIBRIDGE_DIR/pibridge_web/app.py
Restart=always
RestartSec=10
Environment=PIBRIDGE_WEB_HOST=0.0.0.0
Environment=PIBRIDGE_WEB_PORT=$WEB_PORT

[Install]
WantedBy=multi-user.target
EOF
    
    # Hotspot service
    cat > /etc/systemd/system/pibridge-hotspot.service << EOF
[Unit]
Description=PiBridge Hotspot Service
After=network.target
Wants=network.target

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$PIBRIDGE_DIR
ExecStart=/usr/bin/python3 -m pibridge hotspot service
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
    
    # Auto-recovery service
    cat > /etc/systemd/system/pibridge-auto-recovery.service << EOF
[Unit]
Description=PiBridge Auto-Recovery Service
After=network.target
Wants=network.target

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$PIBRIDGE_DIR
ExecStart=/usr/bin/python3 -m pibridge auto-recovery
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF
    
    # Reload systemd
    systemctl daemon-reload
    
    print_status "Systemd services created"
}

# Enable services
enable_services() {
    print_status "Enabling PiBridge services..."
    
    # Enable and start web interface
    systemctl enable pibridge-web
    systemctl start pibridge-web
    
    # Enable auto-recovery by default
    systemctl enable pibridge-auto-recovery
    
    print_status "Services enabled and started"
}

# Configure network interfaces
configure_network() {
    print_status "Configuring network interfaces..."
    
    # Ensure wireless interface is up
    nmcli radio wifi on
    
    print_status "Network configuration complete"
}

# Test installation
test_installation() {
    print_status "Testing PiBridge installation..."
    
    # Wait for web service to start
    sleep 5
    
    # Test web interface
    if curl -s http://localhost:$WEB_PORT/api/health > /dev/null; then
        print_status "Web interface is running successfully"
    else
        print_warning "Web interface test failed"
    fi
    
    # Test API endpoints
    if curl -s http://localhost:$WEB_PORT/api/networks > /dev/null; then
        print_status "Network API is working"
    else
        print_warning "Network API test failed"
    fi
    
    if curl -s http://localhost:$WEB_PORT/api/bridge/pyserial/devices > /dev/null; then
        print_status "Bridge API is working"
    else
        print_warning "Bridge API test failed"
    fi
}

# Display completion message
show_completion_message() {
    echo -e "${GREEN}=== PiBridge Installation Complete ===${NC}"
    echo ""
    echo -e "${BLUE}PiBridge is now installed and running:${NC}"
    echo -e "  Web Interface: http://localhost:$WEB_PORT"
    echo -e "  Configuration: $PIBRIDGE_DIR"
    echo ""
    echo -e "${BLUE}Services:${NC}"
    echo -e "  pibridge-web.service - Web interface"
    echo -e "  pibridge-hotspot.service - Hotspot management"
    echo -e "  pibridge-auto-recovery.service - Auto-recovery"
    echo ""
    echo -e "${BLUE}Management Commands:${NC}"
    echo -e "  systemctl status pibridge-web    - Check web service status"
    echo -e "  systemctl restart pibridge-web   - Restart web interface"
    echo -e "  $PIBRIDGE_DIR/pibridge-cli --help      - PiBridge CLI help"
    echo ""
    echo -e "${YELLOW}Note: The 'gx-developer' bridge profile needs to be created${NC}"
    echo -e "${YELLOW}       manually through the web interface if required.${NC}"
}

# Main installation function
main() {
    echo -e "${BLUE}Starting PiBridge installation...${NC}"
    
    check_root
    install_dependencies
    install_python_deps
    setup_directories
    install_pibridge_files
    setup_services
    enable_services
    configure_network
    test_installation
    show_completion_message
    
    print_status "Installation completed successfully!"
}

# Run main installation
main "$@"