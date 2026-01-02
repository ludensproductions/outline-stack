import platform
import shutil
import os
import stat
import subprocess
import tarfile
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory


from dotenv import load_dotenv


load_dotenv()


class OutlineBackup:
    def __init__(self, outline_volume: str, backup_root: Path | str = Path("./backups")):
        self.outline_volume = outline_volume
        self.backup_root = Path(backup_root).resolve()
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        self.work_dir = self.backup_root / f"{outline_volume}_{self.timestamp}"
        self.archive_path = self.backup_root / f"{outline_volume}_{self.timestamp}.tar.gz"

    def create_backup(self) -> Path:
        """
        Create a compressed backup (.tar.gz) from the Outline Docker volume.

        Returns:
            Path: The path to the created backup archive.
        """
        self.work_dir.mkdir(parents=True, exist_ok=True)

        base_cmd = [
            "docker", "run", "--rm",
            "-v", f"{self.outline_volume}:/volume-data:ro",
            "-v", f"{self.work_dir}:/backup-data",
            "busybox",
            "sh", "-c", "cp -r /volume-data/* /backup-data/ 2>&1 || echo 'Copy failed'"
        ]

        if platform.system() != "Windows":
            full_cmd = ["sudo"] + base_cmd
        else:
            full_cmd = base_cmd.copy()

        print(f"Running backup for volume: {self.outline_volume}")
        result = subprocess.run(full_cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"Backup copy failed: {result.stderr}")

        # Compress using Python stdlib
        print(f"Compressing backup to {self.archive_path}")
        with tarfile.open(self.archive_path, "w:gz") as tar:
            # Add the items in the working directory not the directory itself
            for item in self.work_dir.iterdir():
                tar.add(item, arcname=item.name)

        # Cleanup working directory (handle permission issues from files created by container)
        def _on_rm_error(func, path, exc_info):
            try:
                os.chmod(path, stat.S_IWUSR)
                print(f"Changed permissions for {path}")
            except Exception:
                print(f"Failed to change permissions for {path}")
            try:
                func(path)
                print(f"Removed {path}")
            except Exception:
                print(f"Failed to remove {path} during cleanup.")

        shutil.rmtree(self.work_dir, onerror=_on_rm_error)

        print("Backup created successfully.")
        return self.archive_path

    def restore_backup(self, archive_path: Path | str):
        """
        Restore a backup from a compressed archive to the Outline Docker volume.

        Arguments:
            archive_path (Path | str): Path to the backup archive.
        """
        archive_path = Path(archive_path)
        if not archive_path.is_file():
            raise FileNotFoundError(archive_path)

        temporary_dir = TemporaryDirectory(prefix="restore_")
        temp_restore_dir = Path(temporary_dir.name)
        temp_restore_dir.mkdir(parents=True, exist_ok=True)

        print(f"Extracting backup from {archive_path} to temporary directory.")
        with tarfile.open(archive_path, "r:gz") as tar:
            tar.extractall(path=temp_restore_dir)

        base_cmd = [
            "docker", "run", "--rm",
            "-v", f"{self.outline_volume}:/volume-data",
            "-v", f"{temp_restore_dir}:/restore-data:ro",
            "busybox",
            "sh", "-c", "cp -r /restore-data/* /volume-data/ 2>&1 || echo 'Restore failed'"
        ]

        if platform.system() != "Windows":
            full_cmd = ["sudo"] + base_cmd
        else:
            full_cmd = base_cmd.copy()

        print(f"Restoring backup to volume: {self.outline_volume}")
        result = subprocess.run(full_cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"Backup restore failed: {result.stderr}")

        # Cleanup temporary restore directory
        temporary_dir.cleanup()

        print("Restore completed successfully.")

