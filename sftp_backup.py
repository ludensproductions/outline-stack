import argparse
import os
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

from backup_helper import BackupHelperSFTP
from backup_logger import build_log_entry, log_execution
from outline_backup import OutlineBackup

load_dotenv()


DEBUG = os.getenv("DEBUG", "False").lower() == "true"
REMOTE_BACKUP_DIR = (
    Path("home")
    / "outline_backups"
    / ("compressed" if not DEBUG else "debug_compressed")
)


def get_description(
    current_datetime: datetime,
    total_time: timedelta,
    backup_path: Path,
):
    result = ""
    result += f"**Fecha de ejecución:** <t:{int(current_datetime.timestamp())}:f>\n"
    result += f"**Tiempo total de ejecución:** {total_time}\n"
    result += f"**Backup:** `{backup_path.name}`\n"
    return result


def restore(outline_volume: str):
    sftp_helper = BackupHelperSFTP()
    local_restore_dir = Path("./restores")
    local_restore_dir.mkdir(parents=True, exist_ok=True)

    latest_backup = sftp_helper.download_backup(
        remote_dir=REMOTE_BACKUP_DIR, local_dir=local_restore_dir
    )
    sftp_helper.close()

    backup = OutlineBackup(outline_volume, restore_archive_path=latest_backup)
    backup.restore_backup()

    # Cleanup downloaded restore file
    latest_backup.unlink(missing_ok=True)

    print("Restore completed.")


def backup(outline_volume: str):
    start_time = datetime.now()
    status = "success"
    error = None

    try:
        raise Exception("Test")
        # Step 1: Local backup
        backup = OutlineBackup(outline_volume)
        backup_path = backup.create_backup()

        # Step 2: Incremental upload to SFTP
        sftp_helper = BackupHelperSFTP()

        sftp_helper.upload_backup(
            local_archive=backup_path, remote_dir=REMOTE_BACKUP_DIR
        )

        print(f"Backup created at: {(REMOTE_BACKUP_DIR / backup_path.name).as_posix()}")
        backup_path.unlink(missing_ok=True)
    except Exception as e:
        status = "failure"
        error = str(e)
    finally:
        entry = build_log_entry(
            start_time, status, (datetime.now() - start_time).total_seconds(), error
        )
        log_execution(entry)


if __name__ == "__main__":
    outline_volume = os.getenv("OUTLINE_VOLUME")

    # Either backup or restore based on command line argument flag
    parser = argparse.ArgumentParser(description="Outline Backup and Restore via SFTP")
    parser.add_argument(
        "--restore",
        action="store_true",
        help="Restore the latest backup from SFTP instead of creating a new backup.",
    )
    args = parser.parse_args()

    if args.restore:
        restore(outline_volume)
        exit(0)

    backup(outline_volume)
