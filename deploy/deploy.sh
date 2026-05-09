#!/bin/bash
#
# KVrocks Manager Production Deployment Script
#
# Usage: ./deploy.sh
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
INSTALL_DIR="/opt/kvrocks-manager"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}


# Deploy manually without Docker
deploy_manual() {
    log_info "Manual deployment to $INSTALL_DIR..."

    # Check if running as root
    if [ "$EUID" -ne 0 ]; then
        log_error "Please run as root for manual deployment"
        exit 1
    fi

    # Create user
    if ! id "kvrocks" &>/dev/null; then
        log_info "Creating kvrocks user..."
        useradd -r -s /bin/false kvrocks
    fi

    # Create directories
    log_info "Creating directories..."
    mkdir -p "$INSTALL_DIR"
    mkdir -p /var/log/kvrocks-manager

    # Copy project files
    log_info "Copying project files..."
    cp -r "$PROJECT_DIR/backend" "$INSTALL_DIR/"
    cp -r "$PROJECT_DIR/frontend" "$INSTALL_DIR/"

    # Setup backend
    log_info "Setting up backend..."
    cd "$INSTALL_DIR/backend"
    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt gunicorn

    # Create .env if not exists
    if [ ! -f .env ]; then
        log_info "Creating backend .env file..."
        cat > .env << EOF
DEBUG=false
DATABASE_URL=mysql+aiomysql://kvrocks:YOUR_DB_PASSWORD@localhost:3306/kvrocks_manager
SECRET_KEY=$(openssl rand -hex 32)
REDIS_URL=redis://localhost:6379/0
EOF
        log_warn "Please edit $INSTALL_DIR/backend/.env with your database credentials"
    fi

    # Build frontend
    log_info "Building frontend..."
    cd "$INSTALL_DIR/frontend"
    npm ci
    npm run build

    # Set permissions
    log_info "Setting permissions..."
    chown -R kvrocks:kvrocks "$INSTALL_DIR"
    chown -R kvrocks:kvrocks /var/log/kvrocks-manager

    # Install systemd services
    log_info "Installing systemd services..."
    cp "$PROJECT_DIR/deploy/kvrocks-manager.service" /etc/systemd/system/

    systemctl daemon-reload
    systemctl enable kvrocks-manager

    # Copy nginx config
    if [ -d /etc/nginx ]; then
        log_info "Copying nginx configuration..."
        cp "$PROJECT_DIR/deploy/nginx.conf" /etc/nginx/conf.d/kvrocks-manager.conf
        log_warn "Please edit /etc/nginx/conf.d/kvrocks-manager.conf with your domain and SSL certificates"
    fi

    log_info "Manual deployment complete!"
    echo ""
    echo "Next steps:"
    echo "  1. Configure MySQL database and update $INSTALL_DIR/backend/.env"
    echo "  2. Configure nginx with your domain: /etc/nginx/conf.d/kvrocks-manager.conf"
    echo "  3. Start services:"
    echo "     systemctl start kvrocks-manager"
    echo "     systemctl restart nginx"
    echo ""
    echo "Default login: admin / admin123"
}

# Main
deploy_manual
