#!/bin/bash
set -e
set -a
source .env
set +a

# Create dump inside the container
docker compose exec -T postgres \
  pg_dump -U "$SQL_USER" -d "$SQL_DBNAME" -F c -Z 9 -f /tmp/outline_db.dump

# Copy it out
docker compose cp postgres:/tmp/outline_db.dump ./dumps/outline_db.dump

# Clean up
docker compose exec -T postgres rm /tmp/outline_db.dump

# Borrar dump comprimido en el directorio de dumps de git
if [ -f "$BACKUP_PATH"/outline_db.dump ]; then
  echo "El archivo $BACKUP_PATH/outline_db.dump existe. Procediendo a eliminarlo."
  sudo rm "$BACKUP_PATH"/outline_db.dump
fi

# Mover datos del postgres al directorio de backups
sudo mv ./dumps/outline_db.dump "$BACKUP_PATH/"

# Hacer commit y push de los cambios al repositorio de backups
cd "$BACKUP_PATH" || exit

# Obtener el nombre de la rama actual, si DEBUG es True, usar "test/local", si no "main"
if [ "$DEBUG" = "True" ]; then
  BRANCH_NAME="test/local"
else
  BRANCH_NAME="main"
fi

git add .
git commit -m "backup $(date +%F_%H-%M-%S)"
git push origin $BRANCH_NAME
