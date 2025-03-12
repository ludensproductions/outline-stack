# $POSTGRES_VOLUME = "outline-stack_postgres-data"
# $OUTLINE_VOLUME="outline-stack_outline-data"

$POSTGRES_VOLUME = "outline-stack_postgres-data"
$OUTLINE_VOLUME="outline-stack_outline-data"

$BACKUP_FOLDER = ".\backups\<change_this>"

$POSTGRES_BACKUP = Join-Path $BACKUP_FOLDER $POSTGRES_VOLUME
$OUTLINE_BACKUP = Join-Path $BACKUP_FOLDER $OUTLINE_VOLUME

# Write-Output $POSTGRES_BACKUP
# Write-Output $OUTLINE_BACKUP

# Check if the backup folder exists
if (-Not (Test-Path $BACKUP_FOLDER)) {
    Write-Host "❌ Backup folder '${BACKUP_FOLDER}' does not exist."
    exit 1
}

# Resolve full paths
$PostgresBackupFullPath = (Resolve-Path $POSTGRES_BACKUP).ToString().Replace("\", "/")
$OutlineBackupFullPath  = (Resolve-Path $OUTLINE_BACKUP).ToString().Replace("\", "/")

# Run the Docker restore command
docker run --rm `
    -v "${POSTGRES_VOLUME}:/var/lib/postgresql/data" `
    -v "${PostgresBackupFullPath}:/backup-data" `
    postgres:15 bash -c "cp -rv /backup-data/* /var/lib/postgresql/data && chown -R postgres:postgres /var/lib/postgresql/data"

docker run --rm `
    --user 1000:1000 `
    -v "${OUTLINE_VOLUME}:/var/lib/outline/data" `
    -v "${OutlineBackupFullPath}:/backup-data" `
    docker.getoutline.com/outlinewiki/outline:0.82.0 sh -c "cp -rv /backup-data/* /var/lib/outline/data"
