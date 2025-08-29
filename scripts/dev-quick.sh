#!/bin/bash

# Quick development setup script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_status "Starting quick development environment..."

# Check if .env.development exists
if [ ! -f ".env.development" ]; then
    print_status "Creating .env.development from template..."
    cp .env.template .env.development
fi

# Copy environment file
cp .env.development .env

# Stop any existing containers
print_status "Stopping existing containers..."
docker-compose -f docker-compose.dev.yml down --remove-orphans

# Build and start only essential services first
print_status "Starting database and redis..."
docker-compose -f docker-compose.dev.yml up -d db redis

# Wait for database to be ready
print_status "Waiting for database to be ready..."
sleep 15

# Build and start backend
print_status "Building and starting backend..."
docker-compose -f docker-compose.dev.yml up -d backend

# Wait for backend to be ready
print_status "Waiting for backend to be ready..."
sleep 10

# Run migrations
print_status "Running database migrations..."
docker-compose -f docker-compose.dev.yml exec backend alembic upgrade head || print_error "Migration failed, but continuing..."

# Start frontend
print_status "Starting frontend..."
docker-compose -f docker-compose.dev.yml up -d frontend

print_success "Development environment is ready!"
echo
echo "Services:"
docker-compose -f docker-compose.dev.yml ps
echo
echo "Frontend: http://localhost:3000"
echo "Backend API: http://localhost:8000"
echo "API Documentation: http://localhost:8000/docs"
echo
echo "To view logs: docker-compose -f docker-compose.dev.yml logs -f"
echo "To stop: docker-compose -f docker-compose.dev.yml down"