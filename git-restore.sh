# Set the name of the Docker volume and the backup folder
OUTLINE_VOLUME="outline-stack_outline-data"
POSTGRES_VOLUME="outline-stack_postgres-data"

BACKUP_FOLDER="~/backups/outline-backup"

OUTLINE_BACKUP="${BACKUP_FOLDER}/${OUTLINE_VOLUME}"
POSTGRES_BACKUP="${BACKUP_FOLDER}/${POSTGRES_VOLUME}"

# Check if the backup folder exists
if [ ! -d "$BACKUP_FOLDER" ]; then
    echo "❌ Backup folder '$BACKUP_FOLDER' does not exist."
    exit 1
fi

# Run a temporary busybox container to restore the data into the volume
sudo docker run --rm \
    -v "${POSTGRES_VOLUME}:/var/lib/postgresql/data" \
    -v "${POSTGRES_BACKUP}:/backup-data" \
    postgres:15 bash -c "cp -rv /backup-data/* /var/lib/postgresql/data && chown -R postgres:postgres /var/lib/postgresql/data"

sudo docker run --rm \
    --user 1000:1000 \
    -v "${OUTLINE_VOLUME}:/var/lib/outline/data" \
    -v "${OUTLINE_BACKUP}:/backup-data" \
    docker.getoutline.com/outlinewiki/outline:0.82.0 sh -c "cp -rv /backup-data/* /var/lib/outline/data"
