# Conseguir nombre del volumen a ojo, siempre viene siendo {nombre_del_stack_o_carpeta}_{nombre_volumen}
# sudo docker volume ls

# Extraer
NOMBRE_VOLUMEN=nombre_volumen && sudo docker run --rm -v "${NOMBRE_VOLUMEN}:/volume-data" -v "./${NOMBRE_VOLUMEN}:/backup-data" busybox sh -c 'cp -rv /volume-data/* /backup-data'