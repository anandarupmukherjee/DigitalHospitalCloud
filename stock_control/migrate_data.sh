#!/bin/bash
set -euo pipefail

# Configuration
# Pointing to the CORRECT DB matching user's production data (found in services/data_storage)
SOURCE_DB_PATH="/code/services/data_storage/db.sqlite3"
DUMP_COMPLETE="full_dump.json"

BACKUP_SCRIPT="./backup_database.sh"
FORCE_MIGRATE=${FORCE_MIGRATE:-0}
TIMESTAMP=$(date -u +%Y%m%dT%H%M%SZ)
PRESERVED_POSTGRES_DIR="./backups/postgres_data_preserved_${TIMESTAMP}"

if docker compose version >/dev/null 2>&1; then
    COMPOSE_CMD=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_CMD=(docker-compose)
else
    echo "Neither 'docker compose' nor 'docker-compose' is available."
    exit 1
fi

if [ ! -x "$BACKUP_SCRIPT" ]; then
    echo "Backup script not found or not executable: $BACKUP_SCRIPT"
    echo "Please ensure backup_database.sh is present and executable before migrating."
    exit 1
fi

echo "Step 0: Preparation - Shutting down services..."
"${COMPOSE_CMD[@]}" down

if [ -d "postgres_data" ]; then
    echo "Existing postgres_data directory detected."
    if [ "$FORCE_MIGRATE" != "1" ]; then
        echo "To avoid overwriting existing Postgres data, migration will stop here."
        echo "Set FORCE_MIGRATE=1 to allow overwrite after backup."
        exit 1
    fi
    echo "Backing up existing Postgres data before overwrite..."
    "$BACKUP_SCRIPT"
    mkdir -p ./backups
    echo "Preserving existing postgres_data at $PRESERVED_POSTGRES_DIR"
    mv postgres_data "$PRESERVED_POSTGRES_DIR"
fi

echo "Step 1: Starting Database..."
"${COMPOSE_CMD[@]}" up -d db
echo "Waiting for DB to be ready..."
sleep 15

echo "Step 2: Dumping ALL data from Correct SQLite DB..."
# We map the host directory to /code.
# The source DB is at services/data_storage/db.sqlite3 relative to root.
"${COMPOSE_CMD[@]}" run --rm \
    -e DB_ENGINE=django.db.backends.sqlite3 \
    -e DB_NAME=$SOURCE_DB_PATH \
    web \
    python manage.py dumpdata --exclude auth.permission --exclude contenttypes > $DUMP_COMPLETE

# Note: We exclude contenttypes from dump to let the new DB generate them fresh for the installed apps.
# This prevents conflicts if IDs shifted. Since schemas match, this is usually safe.
# However, if GenericForeignKeys are used, we might need contenttypes.
# User's code has GenericForeignKeys? 'inventory_withdrawal' had no visible ones. 'data_storage' neither.
# Let's try excluding contenttypes first as it's safer for 'loaddata' (which often fails on contenttypes).

echo "Data dumped size: $(du -h $DUMP_COMPLETE | cut -f1)"

echo "Step 3: Applying migrations to new Postgres DB..."
"${COMPOSE_CMD[@]}" run --rm web python manage.py migrate

echo "Step 4: Loading data..."
cat "$DUMP_COMPLETE" | "${COMPOSE_CMD[@]}" run --rm -T web python manage.py loaddata --format=json -

echo "Step 5: Starting Web Service..."
"${COMPOSE_CMD[@]}" up -d web

echo "Migration and Deployment Complete!"
