import argparse
import os
import sys
from datetime import datetime, timezone
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


def download() -> Path:
    sftp_helper = BackupHelperSFTP()
    local_restore_dir = Path("./restores")
    local_restore_dir.mkdir(parents=True, exist_ok=True)

    # Redirect progress prints to stderr so only the archive path goes to stdout,
    # allowing shell scripts to capture it cleanly via $(...) / $(...).
    _stdout, sys.stdout = sys.stdout, sys.stderr
    try:
        latest_backup = sftp_helper.download_backup(
            remote_dir=REMOTE_BACKUP_DIR, local_dir=local_restore_dir
        )
        sftp_helper.close()
    finally:
        sys.stdout = _stdout

    print(latest_backup)
    return latest_backup


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


def backup(outline_volume: str, archive_path: str | None = None):
    start_time = datetime.now(timezone.utc)
    status = "success"
    error = None

    try:
        if archive_path:
            backup_path = Path(archive_path)
        else:
            # Step 1: Local backup via Python
            backup = OutlineBackup(outline_volume)
            backup_path = backup.create_backup()

        # Step 2: Upload to SFTP
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
            start_time,
            status,
            (datetime.now(timezone.utc) - start_time).total_seconds(),
            error,
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
    parser.add_argument(
        "--archive-path",
        help="Path to a pre-created archive to upload (skips local backup creation).",
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help="Download the latest backup from SFTP and print its local path to stdout.",
    )
    args = parser.parse_args()

    if args.restore:
        restore(outline_volume)
        exit(0)

    if args.download:
        download()
        exit(0)

    backup(outline_volume, archive_path=args.archive_path)
