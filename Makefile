# Makefile for filmlist deployment and management

.PHONY: help dev prod build clean logs health test backup restore

# Default target
help:
	@echo "Filmlist Deployment Commands:"
	@echo "  dev        - Deploy development environment"
	@echo "  dev-quick  - Quick development setup (without heavy ML packages)"
	@echo "  prod       - Deploy production environment"
	@echo "  build      - Build all Docker images"
	@echo "  clean      - Clean up containers and volumes"
	@echo "  logs       - Show logs from all services"
	@echo "  health     - Run health checks"
	@echo "  test       - Run tests"
	@echo "  backup     - Create database backup"
	@echo "  restore    - Restore database from backup"
	@echo "  stop       - Stop all services"
	@echo "  restart    - Restart all services"

# Development deployment
dev:
	@echo "Deploying development environment..."
	chmod +x scripts/deploy.sh
	./scripts/deploy.sh development

# Quick development deployment (without heavy ML packages)
dev-quick:
	@echo "Starting quick development environment..."
	chmod +x scripts/dev-quick.sh
	./scripts/dev-quick.sh

# Production deployment
prod:
	@echo "Deploying production environment..."
	chmod +x scripts/deploy.sh
	./scripts/deploy.sh production

# Build all images
build:
	@echo "Building Docker images..."
	docker-compose -f docker-compose.dev.yml build --no-cache
	docker-compose -f docker-compose.prod.yml build --no-cache

# Clean up
clean:
	@echo "Cleaning up containers and volumes..."
	docker-compose -f docker-compose.dev.yml down --volumes --remove-orphans
	docker-compose -f docker-compose.prod.yml down --volumes --remove-orphans
	docker system prune -f

# Show logs
logs:
	@echo "Showing logs from all services..."
	docker-compose logs -f

# Health check
health:
	@echo "Running health checks..."
	chmod +x scripts/health_check.sh
	./scripts/health_check.sh

# Run tests
test:
	@echo "Running tests..."
	docker-compose -f docker-compose.dev.yml exec backend pytest -v

# Database backup
backup:
	@echo "Creating database backup..."
	docker-compose -f docker-compose.prod.yml exec db_backup /backup.sh

# Database restore (requires BACKUP_FILE environment variable)
restore:
	@echo "Restoring database from backup..."
	@if [ -z "$(BACKUP_FILE)" ]; then \
		echo "Error: BACKUP_FILE environment variable is required"; \
		echo "Usage: make restore BACKUP_FILE=/path/to/backup.sql.gz"; \
		exit 1; \
	fi
	docker-compose -f docker-compose.prod.yml exec -T db psql -U filmlist -d filmlist < $(BACKUP_FILE)

# Stop services
stop:
	@echo "Stopping all services..."
	docker-compose -f docker-compose.dev.yml down
	docker-compose -f docker-compose.prod.yml down

# Restart services
restart:
	@echo "Restarting services..."
	docker-compose restart

# Development specific commands
dev-logs:
	docker-compose -f docker-compose.dev.yml logs -f

dev-shell:
	docker-compose -f docker-compose.dev.yml exec backend /bin/bash

dev-db:
	docker-compose -f docker-compose.dev.yml exec db psql -U filmlist -d filmlist

# Production specific commands
prod-logs:
	docker-compose -f docker-compose.prod.yml logs -f

prod-shell:
	docker-compose -f docker-compose.prod.yml exec backend /bin/bash

prod-db:
	docker-compose -f docker-compose.prod.yml exec db psql -U filmlist -d filmlist