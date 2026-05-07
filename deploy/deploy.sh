#!/bin/bash
#
# KVrocks Manager Production Deployment Script
#
# Usage: ./deploy.sh [docker|manual]
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

# Deploy using Docker Compose
deploy_docker() {
    log_info "Deploying with Docker Compose..."

    cd "$PROJECT_DIR"

    # Check if .env exists
    if [ ! -f .env ]; then
        log_warn ".env file not found, copying from .env.example"
        cp .env.example .env
        log_warn "Please edit .env file with your configuration"
        exit 1
    fi

    # Build and start containers
    docker-compose build
    docker-compose up -d

    log_info "Waiting for services to start..."
    sleep 10

    # Health check
    if curl -sf http://localhost:8000/health > /dev/null; then
        log_info "Backend is healthy"
    else
        log_error "Backend health check failed"
        docker-compose logs backend
        exit 1
    fi

    log_info "Deployment complete!"
    echo ""
    echo "Services:"
    echo "  - Frontend: http://localhost"
    echo "  - Backend API: http://localhost:8000"
    echo "  - API Docs: http://localhost:8000/docs"
    echo ""
    echo "Default login: admin / admin123"
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
DATABASE_URL=mysql+pymysql://kvrocks:YOUR_DB_PASSWORD@localhost:3306/kvrocks_manager
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
        cp "$PROJECT_DIR/deploy/nginx.conf" /etc/nginx/sites-available/kvrocks-manager
        ln -sf /etc/nginx/sites-available/kvrocks-manager /etc/nginx/sites-enabled/
        log_warn "Please edit /etc/nginx/sites-available/kvrocks-manager with your domain and SSL certificates"
    fi

    log_info "Manual deployment complete!"
    echo ""
    echo "Next steps:"
    echo "  1. Configure MySQL database and update $INSTALL_DIR/backend/.env"
    echo "  2. Configure nginx with your domain: /etc/nginx/sites-available/kvrocks-manager"
    echo "  3. Start services:"
    echo "     systemctl start kvrocks-manager"
    echo "     systemctl restart nginx"
    echo ""
    echo "Default login: admin / admin123"
}

# Main
case "${1:-docker}" in
    docker)
        deploy_docker
        ;;
    manual)
        deploy_manual
        ;;
    *)
        echo "Usage: $0 [docker|manual]"
        echo ""
        echo "  docker  - Deploy using Docker Compose (default)"
        echo "  manual  - Deploy manually with systemd services"
        exit 1
        ;;
esac
