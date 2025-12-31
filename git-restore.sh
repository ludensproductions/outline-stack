#!/bin/bash
set -e

# Check if dump file path is provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 <path-to-dump-file>"
    echo "Example: $0 ./backups/outline.dump"
    exit 1
fi

DUMP_FILE="$1"

# Check if dump file exists
if [ ! -f "$DUMP_FILE" ]; then
    echo "Error: Dump file '$DUMP_FILE' not found"
    exit 1
fi

set -a
source .env
set +a

echo "Restoring database from: $DUMP_FILE"
echo "Warning: This will delete the existing database '$SQL_DBNAME'"
read -p "Are you sure you want to continue? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Restore cancelled"
    exit 0
fi

# Drop the database
echo "Dropping database..."
docker compose exec -T postgres \
  dropdb -U "$SQL_USER" "$SQL_DBNAME" --if-exists

# Create a fresh database
echo "Creating fresh database..."
docker compose exec -T postgres \
  createdb -U "$SQL_USER" "$SQL_DBNAME"

# Copy dump file into container
echo "Copying dump file to container..."
docker compose cp "$DUMP_FILE" postgres:/tmp/restore.dump

# Restore the database
echo "Restoring database..."
docker compose exec -T postgres \
  pg_restore -U "$SQL_USER" -d "$SQL_DBNAME" -v /tmp/restore.dump

# Clean up
echo "Cleaning up..."
docker compose exec -T postgres rm /tmp/restore.dump

echo "Database restored successfully!"
