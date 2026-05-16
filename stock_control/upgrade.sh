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

BACKUP_SCRIPT="./backup_database.sh"
SKIP_BACKUP=${SKIP_BACKUP:-0}
SKIP_BUILD=${SKIP_BUILD:-0}

if [ "$SKIP_BACKUP" != "1" ]; then
  if [ ! -x "$BACKUP_SCRIPT" ]; then
    echo "Backup script not found or not executable: $BACKUP_SCRIPT"
    exit 1
  fi
  echo "Step 1: Creating pre-upgrade backup..."
  "$BACKUP_SCRIPT"
else
  echo "Step 1: Skipping backup because SKIP_BACKUP=1"
fi

if [ "$SKIP_BUILD" != "1" ]; then
  echo "Step 2: Building updated images..."
  "${COMPOSE_CMD[@]}" build
else
  echo "Step 2: Skipping image build because SKIP_BUILD=1"
fi

echo "Step 3: Starting upgraded stack..."
"${COMPOSE_CMD[@]}" up -d

echo "Upgrade complete."
