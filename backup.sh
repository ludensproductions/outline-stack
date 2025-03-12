# Conseguir nombre del volumen a ojo, siempre viene siendo {nombre_del_stack_o_carpeta}_{nombre_volumen}
# sudo docker volume ls

# Extraer
OUTLINE_VOLUME=outline-data && sudo docker run --rm \
    -v "${OUTLINE_VOLUME}:/var/lib/outline/data" \
    -v "./${OUTLINE_VOLUME}:/backup-data" \
    busybox sh -c 'cp -rv /var/lib/outline/data/* /backup-data'

POSTGRES_VOLUME=postgres-data && sudo docker run --rm \
    -v "${POSTGRES_VOLUME}:/var/lib/postgresql/data" \
    -v "./${POSTGRES_VOLUME}:/backup-data" \
    busybox sh -c 'cp -rv /var/lib/postgresql/data/* /backup-data'

find ./backups -maxdepth 1 -type d -name 'backup_*' -mtime +7 -exec echo Deleting {} \;

BACKUP_DIR_NAME="backup_$(date +%F_%H-%M-%S)"
BACKUP_DIR="./backups/${BACKUP_DIR_NAME}"

mkdir ${BACKUP_DIR}

sudo mv postgres-data/ "${BACKUP_DIR}"
sudo mv outline-data/ "${BACKUP_DIR}"
