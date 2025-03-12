# Powershell Script for local testing

# Define the volume and backup directory name
$POSTGRES_VOLUME = "outline-stack_postgres-data"
$OUTLINE_VOLUME = "outline-stack_outline-data"
$BACKUP_DIR_NAME = "backup_$(Get-Date -Format 'yyyy-MM-dd_HH-mm-ss')"
$BACKUP_DIR = ".\backups\$BACKUP_DIR_NAME"

# Create backup directory
New-Item -ItemType Directory -Force -Path ${BACKUP_DIR}

# Run Docker to copy data from the volume to the backup directory
docker run --rm -v "${POSTGRES_VOLUME}:/volume-data" -v "$PWD\${POSTGRES_VOLUME}:/backup-data" busybox sh -c 'cp -rv /volume-data/* /backup-data'
docker run --rm -v "${OUTLINE_VOLUME}:/volume-data" -v "$PWD\${OUTLINE_VOLUME}:/backup-data" busybox sh -c 'cp -rv /volume-data/* /backup-data'

# Delete backups older than 7 days
$sevenDaysAgo = (Get-Date).AddDays(-7)
Get-ChildItem -Path .\backups\ -Directory -Recurse | Where-Object { $_.Name -like 'backup_*' -and $_.CreationTime -lt $sevenDaysAgo } | ForEach-Object {
    Write-Host "Deleting $_"
    Remove-Item $_.FullName -Recurse -Force
}

# Move data from Postgres and Outline to the backup folder
Move-Item -Path ".\${POSTGRES_VOLUME}" -Destination $BACKUP_DIR
Move-Item -Path ".\${OUTLINE_VOLUME}" -Destination $BACKUP_DIR
