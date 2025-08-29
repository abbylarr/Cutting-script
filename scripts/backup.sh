#!/bin/bash

# Database backup script for filmlist

set -e

# Configuration
DB_HOST="db"
DB_NAME="${POSTGRES_DB:-filmlist}"
DB_USER="${POSTGRES_USER:-filmlist}"
BACKUP_DIR="/backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/filmlist_backup_${DATE}.sql"
RETENTION_DAYS=7

# Create backup directory if it doesn't exist
mkdir -p "${BACKUP_DIR}"

# Create database backup
echo "Creating database backup..."
pg_dump -h "${DB_HOST}" -U "${DB_USER}" -d "${DB_NAME}" > "${BACKUP_FILE}"

# Compress backup
gzip "${BACKUP_FILE}"
BACKUP_FILE="${BACKUP_FILE}.gz"

echo "Backup created: ${BACKUP_FILE}"

# Remove old backups (keep only last 7 days)
find "${BACKUP_DIR}" -name "filmlist_backup_*.sql.gz" -mtime +${RETENTION_DAYS} -delete

echo "Old backups cleaned up (retention: ${RETENTION_DAYS} days)"

# Log backup completion
echo "$(date): Backup completed successfully" >> "${BACKUP_DIR}/backup.log"