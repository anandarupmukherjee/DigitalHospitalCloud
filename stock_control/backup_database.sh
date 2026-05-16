#!/bin/bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "$0")" && pwd)
cd "$ROOT_DIR"

if docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE_CMD=(docker-compose)
else
  echo "Neither 'docker compose' nor 'docker-compose' is available."
  exit 1
fi

write_checksum() {
  local target="$1"
  sha256sum "$target" > "${target}.sha256"
}

BACKUP_DIR="./backups"
mkdir -p "$BACKUP_DIR"
TIMESTAMP=$(date -u +%Y%m%dT%H%M%SZ)
SOURCE_DB="./services/data_storage/db.sqlite3"
SQLITE_BACKUP="$BACKUP_DIR/histopath_sqlite_${TIMESTAMP}.sqlite3"
POSTGRES_DATA_ARCHIVE="$BACKUP_DIR/histopath_postgres_data_${TIMESTAMP}.tar.gz"
POSTGRES_SQL_DUMP="$BACKUP_DIR/histopath_db_${TIMESTAMP}.dump"

echo "Backing up database state to $BACKUP_DIR"

if [ -f "$SOURCE_DB" ]; then
  echo "- Copying SQLite source database..."
  cp -p "$SOURCE_DB" "$SQLITE_BACKUP"
  write_checksum "$SQLITE_BACKUP"
  echo "  Saved SQLite backup: $SQLITE_BACKUP"
else
  echo "- No SQLite source database found at $SOURCE_DB; skipping SQLite backup."
fi

if [ -d "postgres_data" ]; then
  echo "- Archiving existing Postgres data directory..."
  tar -czf "$POSTGRES_DATA_ARCHIVE" postgres_data
  write_checksum "$POSTGRES_DATA_ARCHIVE"
  echo "  Saved Postgres volume archive: $POSTGRES_DATA_ARCHIVE"
else
  echo "- No postgres_data directory found; skipping Postgres data directory backup."
fi

if "${COMPOSE_CMD[@]}" ps db >/dev/null 2>&1; then
  DB_CONTAINER_STATUS=$("${COMPOSE_CMD[@]}" ps --status running --services 2>/dev/null | grep -Fx "db" || true)
  if [ -n "$DB_CONTAINER_STATUS" ]; then
    echo "- Dumping live Postgres database..."
    "${COMPOSE_CMD[@]}" exec -T db pg_dump -Fc -U histopath -d histopath > "$POSTGRES_SQL_DUMP"
    write_checksum "$POSTGRES_SQL_DUMP"
    echo "  Saved Postgres dump: $POSTGRES_SQL_DUMP"
  else
    echo "- Postgres service exists but is not running; skipping live pg_dump."
    echo "  Start the db service and rerun this script if you want a live dump."
  fi
else
  echo "- Postgres container is not running; skipping live Postgres SQL dump."
  echo "  Start the db service and rerun this script if you want a live pg_dump."
fi

echo "Backup complete."
