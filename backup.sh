# Conseguir nombre del volumen a ojo, siempre viene siendo {nombre_del_stack_o_carpeta}_{nombre_volumen}
# sudo docker volume ls

# Extraer
OUTLINE_VOLUME=outline-data && sudo docker run --rm \
    -v "${OUTLINE_VOLUME}:/volume-data" \
    -v "./${OUTLINE_VOLUME}:/backup-data" \
    busybox sh -c 'cp -rv /volume-data/* /backup-data'

POSTGRES_VOLUME=postgres-data && sudo docker run --rm \
    -v "${POSTGRES_VOLUME}:/volume-data" \
    -v "./${POSTGRES_VOLUME}:/backup-data" \
    busybox sh -c 'cp -rv /volume-data/* /backup-data'

# Borrar backups viejos con mas de 7 dias de antiguedad
find ./backups -maxdepth 1 -type d -name 'backup_*' -mtime +7 -exec echo Deleting {} \;

# Crea directorio para guardar el backup nuevo
BACKUP_DIR_NAME="backup_$(date +%F_%H-%M-%S)"
BACKUP_DIR="./backups/${BACKUP_DIR_NAME}"

mkdir ${BACKUP_DIR}

# Mover datos del outline y postgres al directorio de backups
sudo mv postgres-data/ "${BACKUP_DIR}"
sudo mv outline-data/ "${BACKUP_DIR}"
