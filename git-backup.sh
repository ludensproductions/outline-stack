# Conseguir nombre del volumen a ojo, siempre viene siendo {nombre_del_stack_o_carpeta}_{nombre_volumen}
# sudo docker volume ls
OUTLINE_VOLUME="outline-stack_outline-data"
POSTGRES_VOLUME="outline-stack_postgres-data"

cd ~/backups/outline-backup
sudo rm -rf ./${POSTGRES_VOLUME}
sudo rm -rf ./${OUTLINE_VOLUME}

cd ~/deploys/outline-stack

# Extraer
sudo docker run --rm -v "${OUTLINE_VOLUME}:/volume-data" -v "./backups/${OUTLINE_VOLUME}:/backup-data" busybox sh -c 'cp -rv /volume-data/* /backup-data'
sudo docker run --rm -v "${POSTGRES_VOLUME}:/volume-data" -v "./backups/${POSTGRES_VOLUME}:/backup-data" busybox sh -c 'cp -rv /volume-data/* /backup-data'

# Mover datos del outline y postgres al directorio de backups
sudo mv ./backups/${POSTGRES_VOLUME} ~/backups/outline-backup
sudo mv ./backups/${OUTLINE_VOLUME} ~/backups/outline-backup

cd ~/backups/outline-backup

sudo git add .
sudo git commit -m "backup $(date +%F_%H-%M-%S)"
git push origin main
