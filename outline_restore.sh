#!/usr/bin/env bash
set -euo pipefail

# Run from the project root alongside sftp_backup.py

if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

OUTLINE_VOLUME="${OUTLINE_VOLUME:?OUTLINE_VOLUME is required}"
SQL_USER="${SQL_USER:?SQL_USER is required}"
SQL_DBNAME="${SQL_DBNAME:?SQL_DBNAME is required}"

TEMP_DIR=""

cleanup() {
    [ -n "${TEMP_DIR}" ] && [ -d "${TEMP_DIR}" ] && sudo rm -rf "${TEMP_DIR}" 2>/dev/null || true
}
trap cleanup EXIT

# 1. Download latest backup from SFTP (progress goes to stderr, path to stdout)
echo "Downloading latest backup..."
ARCHIVE_PATH="$(python sftp_backup.py --download)"
echo "Downloaded: ${ARCHIVE_PATH}"

# 2. Extract archive
TEMP_DIR="$(mktemp -d -t restore_XXXXXX)"
echo "Extracting backup from ${ARCHIVE_PATH}..."
tar -xzf "${ARCHIVE_PATH}" -C "${TEMP_DIR}"

MEDIA_DIR="${TEMP_DIR}/media"
DB_DUMP="${TEMP_DIR}/db/outline_db.dump"

if [ ! -d "${MEDIA_DIR}" ]; then
    echo "ERROR: Missing media directory in backup" >&2
    exit 1
fi

if [ ! -f "${DB_DUMP}" ]; then
    echo "ERROR: Missing database dump in backup" >&2
    exit 1
fi

# 3. Restore media volume (clean + copy, sudo matches original Python behavior on Linux)
echo "Restoring media volume (clean overwrite)..."
sudo docker run --rm \
    -v "${OUTLINE_VOLUME}:/volume-data" \
    -v "$(cd "${MEDIA_DIR}" && pwd):/restore-data:ro" \
    busybox \
    sh -c "rm -rf /volume-data/* && cp -a /restore-data/. /volume-data/"

# 4. Restore database
echo "Restoring database..."
docker compose exec -T postgres pg_restore \
    -U "${SQL_USER}" \
    -d "${SQL_DBNAME}" \
    --clean \
    --if-exists < "${DB_DUMP}"

# Cleanup downloaded archive (only reached on success)
rm -f "${ARCHIVE_PATH}"

echo "Restore completed."
