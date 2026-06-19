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

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_ROOT="./backups"
WORK_DIR="${BACKUP_ROOT}/${OUTLINE_VOLUME}_${TIMESTAMP}"
ARCHIVE_PATH="${BACKUP_ROOT}/${OUTLINE_VOLUME}_${TIMESTAMP}.tar.gz"
STAGE_DIR=""

cleanup() {
    [ -d "${WORK_DIR}" ] && sudo rm -rf "${WORK_DIR}" 2>/dev/null || true
    [ -n "${STAGE_DIR}" ] && [ -d "${STAGE_DIR}" ] && sudo rm -rf "${STAGE_DIR}" 2>/dev/null || true
}
trap cleanup EXIT

mkdir -p "${WORK_DIR}"

# 1. Dump DB
echo "Dumping database..."
docker compose exec -T postgres pg_dump \
    -U "${SQL_USER}" \
    -d "${SQL_DBNAME}" \
    -F c \
    -Z 9 > "${WORK_DIR}/outline_db.dump"

if [ ! -s "${WORK_DIR}/outline_db.dump" ]; then
    echo "ERROR: DB dump is empty (silent failure)" >&2
    exit 1
fi

# 2. Copy volume (sudo matches original Python behavior on Linux)
echo "Copying volume: ${OUTLINE_VOLUME}"
sudo docker run --rm \
    -v "${OUTLINE_VOLUME}:/volume-data:ro" \
    -v "$(cd "${WORK_DIR}" && pwd):/backup-data" \
    busybox \
    sh -c "cp -a /volume-data/. /backup-data/ 2>/dev/null || true"

# 3. Create archive with db/ and media/ structure expected by restore
echo "Creating archive: ${ARCHIVE_PATH}"
STAGE_DIR="$(mktemp -d)"
mkdir -p "${STAGE_DIR}/db" "${STAGE_DIR}/media"

mv "${WORK_DIR}/outline_db.dump" "${STAGE_DIR}/db/"
sudo cp -rp "${WORK_DIR}/." "${STAGE_DIR}/media/"

mkdir -p "${BACKUP_ROOT}"
tar -czf "${ARCHIVE_PATH}" -C "${STAGE_DIR}" .

echo "Archive created: ${ARCHIVE_PATH}"

# 4. Upload via SFTP
echo "Uploading to SFTP..."
python sftp_backup.py --archive-path "${ARCHIVE_PATH}"

echo "Backup completed successfully."
