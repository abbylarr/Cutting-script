#!/bin/bash

# Health check script for filmlist services

set -e

# Configuration
BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"
FRONTEND_URL="${FRONTEND_URL:-http://localhost:3000}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6379}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to check service health
check_service() {
    local service_name="$1"
    local check_command="$2"
    
    echo -n "Checking ${service_name}... "
    
    if eval "$check_command" >/dev/null 2>&1; then
        echo -e "${GREEN}OK${NC}"
        return 0
    else
        echo -e "${RED}FAILED${NC}"
        return 1
    fi
}

# Function to check HTTP endpoint
check_http() {
    local url="$1"
    curl -f -s --max-time 10 "$url" >/dev/null
}

# Function to check database
check_database() {
    pg_isready -h "$DB_HOST" -p "$DB_PORT" >/dev/null
}

# Function to check Redis
check_redis() {
    redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ping >/dev/null
}

echo "=== Filmlist Health Check ==="
echo "Timestamp: $(date)"
echo

# Check all services
failed=0

check_service "Database" "check_database" || ((failed++))
check_service "Redis" "check_redis" || ((failed++))
check_service "Backend API" "check_http ${BACKEND_URL}/health" || ((failed++))
check_service "Backend Detailed Health" "check_http ${BACKEND_URL}/health/detailed" || ((failed++))

# Check frontend only if it's expected to be running
if [ "$FRONTEND_URL" != "http://localhost:3000" ] || nc -z localhost 3000 2>/dev/null; then
    check_service "Frontend" "check_http ${FRONTEND_URL}" || ((failed++))
fi

echo

# Summary
if [ $failed -eq 0 ]; then
    echo -e "${GREEN}All services are healthy!${NC}"
    exit 0
else
    echo -e "${RED}${failed} service(s) failed health check${NC}"
    exit 1
fi