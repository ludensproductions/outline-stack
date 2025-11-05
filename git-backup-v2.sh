#!/bin/bash
set -e

# === CONFIGURATION ===
OUTLINE_VOLUME="outline-stack_outline-data"
POSTGRES_VOLUME="outline-stack_postgres-data"

# Local paths
BACKUP_DIR="$HOME/backups/outline-backup"
DEPLOY_DIR="$HOME/deploys/outline-stack"

# SFTP remote configuration
SFTP_USER="backupuser"
SFTP_HOST="backup.example.com"
SFTP_REMOTE_DIR="/remote/backups/outline-data"

# === CLEAN PREVIOUS TEMP BACKUPS ===
cd "$BACKUP_DIR"
sudo rm -rf "./${POSTGRES_VOLUME}"

cd "$DEPLOY_DIR"
sudo rm -rf "./backups/${POSTGRES_VOLUME}"
sudo rm -rf "./backups/${OUTLINE_VOLUME}"

# === EXTRACT POSTGRES DATA (for Git) ===
sudo docker run --rm \
  -v "${POSTGRES_VOLUME}:/volume-data" \
  -v "./backups/${POSTGRES_VOLUME}:/backup-data" \
  busybox sh -c 'cp -rv /volume-data/* /backup-data'

# === MOVE POSTGRES BACKUP TO GIT DIRECTORY ===
sudo mv "./backups/${POSTGRES_VOLUME}" "$BACKUP_DIR"

# === COMMIT AND PUSH POSTGRES BACKUP TO GITHUB ===
cd "$BACKUP_DIR"
sudo git add .
sudo git commit -m "backup $(date +%F_%H-%M-%S)" || echo "No changes to commit"
git push origin main || echo "⚠️ Git push failed — check repository size or credentials"

# === EXTRACT OUTLINE DATA (for SFTP) ===
cd "$DEPLOY_DIR"
sudo docker run --rm \
  -v "${OUTLINE_VOLUME}:/volume-data" \
  -v "./backups/${OUTLINE_VOLUME}:/backup-data" \
  busybox sh -c 'cp -rv /volume-data/* /backup-data'

# === UPLOAD OUTLINE DATA VIA SFTP ===
echo "Uploading Outline data via SFTP..."
cd "$DEPLOY_DIR/backups"

# Optional: compress before sending to reduce transfer size
tar czf "${OUTLINE_VOLUME}_$(date +%F_%H-%M-%S).tar.gz" "${OUTLINE_VOLUME}"

# Upload the tarball
sftp "${SFTP_USER}@${SFTP_HOST}" <<EOF
mkdir -p ${SFTP_REMOTE_DIR}
cd ${SFTP_REMOTE_DIR}
put ${OUTLINE_VOLUME}_$(date +%F_%H-%M-%S).tar.gz
bye
EOF

echo "✅ Outline data uploaded successfully to SFTP server."

# === CLEANUP LOCAL COPIES OF OUTLINE DATA ===
sudo rm -rf "./backups/${OUTLINE_VOLUME}"

