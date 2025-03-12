# Conseguir nombre del volumen a ojo, siempre viene siendo {nombre_del_stack_o_carpeta}_{nombre_volumen}
# sudo docker volume ls

# Extraer
OUTLINE_VOLUME=outline-data && sudo docker run --rm \
    -v "${OUTLINE_VOLUME}:/var/lib/outline/data" \
    -v "./${OUTLINE_VOLUME}:/backup-data" \
    busybox sh -c 'cp -rv /volume-data/* /backup-data'

POSTGRES_VOLUME=postgres-data && sudo docker run --rm \
    -v "${POSTGRES_VOLUME}:/var/lib/postgresql/data" \
    -v "./${POSTGRES_VOLUME}:/backup-data" \
    busybox sh -c 'cp -rv /volume-data/* /backup-data'
