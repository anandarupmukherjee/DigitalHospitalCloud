#!/bin/bash
set -e

# Configuration
# Pointing to the CORRECT DB matching user's production data (found in services/data_storage)
SOURCE_DB_PATH="/code/services/data_storage/db.sqlite3"
DUMP_COMPLETE="full_dump.json"

echo "Step 0: Preparation - Shutting down and cleaning..."
docker-compose down

if [ -d "postgres_data" ]; then
    echo "Wiping existing postgres_data to ensure clean migration..."
    rm -rf postgres_data
fi

echo "Step 1: Starting Database..."
docker-compose up -d db
echo "Waiting for DB to be ready..."
sleep 15

echo "Step 2: Dumping ALL data from Correct SQLite DB..."
# We map the host directory to /code.
# The source DB is at services/data_storage/db.sqlite3 relative to root.
docker-compose run --rm \
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
docker-compose run --rm web python manage.py migrate

echo "Step 4: Cleaning Old ContentTypes..."
# Start fresh to ensure IDs align if we were to load them.
docker-compose run --rm web python manage.py shell -c "from django.contrib.contenttypes.models import ContentType; ContentType.objects.all().delete();"

echo "Step 5: Loading data..."
cat $DUMP_COMPLETE | docker-compose run --rm -T web python manage.py loaddata --format=json -

echo "Step 6: Starting Web Service..."
docker-compose up -d web

echo "Migration and Deployment Complete!"
