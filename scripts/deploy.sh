#!/bin/bash

# Deployment script for filmlist

set -e

# Configuration
ENVIRONMENT="${1:-development}"
COMPOSE_FILE=""
ENV_FILE=""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."
    
    # Check if Docker is installed and running
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed"
        exit 1
    fi
    
    if ! docker info &> /dev/null; then
        print_error "Docker is not running"
        exit 1
    fi
    
    # Check if Docker Compose is installed
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed"
        exit 1
    fi
    
    print_success "Prerequisites check passed"
}

# Function to set environment-specific configuration
set_environment() {
    case "$ENVIRONMENT" in
        "development"|"dev")
            COMPOSE_FILE="docker-compose.dev.yml"
            ENV_FILE=".env.development"
            print_status "Setting up development environment"
            ;;
        "production"|"prod")
            COMPOSE_FILE="docker-compose.prod.yml"
            ENV_FILE=".env.production"
            print_status "Setting up production environment"
            ;;
        *)
            print_error "Invalid environment: $ENVIRONMENT"
            print_error "Valid options: development, production"
            exit 1
            ;;
    esac
}

# Function to validate environment variables
validate_env() {
    print_status "Validating environment variables..."
    
    if [ ! -f "$ENV_FILE" ]; then
        print_warning "Environment file $ENV_FILE not found, using .env.template"
        cp .env.template "$ENV_FILE"
    fi
    
    # Check required variables
    source "$ENV_FILE"
    
    if [ -z "$OPENAI_API_KEY" ] || [ "$OPENAI_API_KEY" = "your_openai_api_key_here" ]; then
        print_error "OPENAI_API_KEY is not set or using default value"
        print_error "Please set your OpenAI API key in $ENV_FILE"
        exit 1
    fi
    
    if [ "$ENVIRONMENT" = "production" ]; then
        if [ -z "$SECRET_KEY" ] || [ "$SECRET_KEY" = "your-secret-key-change-in-production" ]; then
            print_error "SECRET_KEY is not set or using default value"
            print_error "Please set a secure secret key in $ENV_FILE"
            exit 1
        fi
        
        if [ -z "$POSTGRES_PASSWORD" ]; then
            print_error "POSTGRES_PASSWORD is not set for production"
            exit 1
        fi
    fi
    
    print_success "Environment validation passed"
}

# Function to build and start services
deploy_services() {
    print_status "Building and starting services..."
    
    # Copy environment file
    cp "$ENV_FILE" .env
    
    # Build and start services
    docker-compose -f "$COMPOSE_FILE" down --remove-orphans
    docker-compose -f "$COMPOSE_FILE" build --no-cache
    docker-compose -f "$COMPOSE_FILE" up -d
    
    print_success "Services started successfully"
}

# Function to run database migrations
run_migrations() {
    print_status "Running database migrations..."
    
    # Wait for database to be ready
    sleep 10
    
    # Run Alembic migrations
    docker-compose -f "$COMPOSE_FILE" exec backend alembic upgrade head
    
    print_success "Database migrations completed"
}

# Function to verify deployment
verify_deployment() {
    print_status "Verifying deployment..."
    
    # Wait for services to start
    sleep 30
    
    # Run health checks
    if [ -f "scripts/health_check.sh" ]; then
        chmod +x scripts/health_check.sh
        ./scripts/health_check.sh
    else
        print_warning "Health check script not found, skipping verification"
    fi
    
    print_success "Deployment verification completed"
}

# Function to show deployment info
show_info() {
    print_success "Deployment completed successfully!"
    echo
    echo "Environment: $ENVIRONMENT"
    echo "Compose file: $COMPOSE_FILE"
    echo "Environment file: $ENV_FILE"
    echo
    echo "Services:"
    docker-compose -f "$COMPOSE_FILE" ps
    echo
    
    if [ "$ENVIRONMENT" = "development" ]; then
        echo "Frontend: http://localhost:3000"
        echo "Backend API: http://localhost:8000"
        echo "API Documentation: http://localhost:8000/docs"
    else
        echo "Application: http://localhost"
        echo "API Documentation: http://localhost/api/v1/docs"
    fi
}

# Main deployment flow
main() {
    echo "=== Filmlist Deployment Script ==="
    echo "Environment: $ENVIRONMENT"
    echo "Timestamp: $(date)"
    echo
    
    check_prerequisites
    set_environment
    validate_env
    deploy_services
    run_migrations
    verify_deployment
    show_info
}

# Show usage if no arguments provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 <environment>"
    echo "Environments: development, production"
    exit 1
fi

# Run main function
main