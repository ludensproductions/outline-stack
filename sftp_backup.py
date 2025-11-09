import os
import stat
import subprocess
from datetime import datetime
from pathlib import Path


import paramiko
from dotenv import load_dotenv


load_dotenv()


class OutlineBackup:
    def __init__(self, outline_volume: str, backup_root: Path | str = Path("./backups")):
        self.outline_volume = outline_volume
        self.backup_root = Path(backup_root).resolve()
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_dir = self.backup_root / f"{outline_volume}_{self.timestamp}"

    def create_backup(self) -> Path:
        """Create a local backup from the Outline Docker volume."""
        self.output_dir.mkdir(parents=True, exist_ok=True)

        cmd = [
            "sudo",
            "docker", "run", "--rm",
            "-v", f"{self.outline_volume}:/volume-data",
            "-v", f"{self.output_dir}:/backup-data",
            "busybox",
            "sh", "-c", "cp -rv /volume-data/* /backup-data"
        ]

        print(f"🧱 Running backup for volume: {self.outline_volume}")
        print(" ".join(cmd))

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print("❌ Backup failed!")
            print(result.stderr)
            raise RuntimeError("Backup command failed.")

        print("✅ Backup completed successfully.")
        print(result.stdout)
        return self.output_dir


    def delete_backup(self):
        """Delete the local backup folder recursively using pathlib."""
        if not self.output_dir.exists():
            print(f"Folder not found: {self.output_dir}")
            return

        # Recursively delete children first
        for path in sorted(self.output_dir.rglob("*"), reverse=True):
            if path.is_file() or path.is_symlink():
                path.unlink()
            elif path.is_dir():
                path.rmdir()

        # Finally remove the root backup folder
        self.output_dir.rmdir()

        print(f"🗑️ Deleted backup folder: {self.output_dir}")


    def delete_remote_folder(self, remote_folder: Path | str):
        """Delete a remote folder recursively using SFTP."""
        self._init_connection()

        remote_folder = Path(remote_folder).as_posix()

        # Ensure folder exists
        try:
            self.sftp.stat(remote_folder)
        except FileNotFoundError:
            print(f"Remote folder not found: {remote_folder}")
            return

        def _delete_recursive(path: str):
            for item in self.sftp.listdir_attr(path):
                item_path = f"{path}/{item.filename}"

                # Directory
                if self.sftp.stat.S_ISDIR(item.st_mode):
                    _delete_recursive(item_path)
                    self.sftp.rmdir(item_path)

                # File
                else:
                    self.sftp.remove(item_path)


class BackupHelperSFTP:
    
    def __init__(self):
        self.FTP_HOST = os.getenv("FTP_HOST")
        self.FTP_PORT = int(os.getenv("FTP_PORT", "22"))  # SFTP default = 22
        self.FTP_USERNAME = os.getenv("FTP_USERNAME")
        self.FTP_PASSWORD = os.getenv("FTP_PASSWORD")

        self.ssh_client = None
        self.sftp = None


    def _init_connection(self):
        """Initialize SSH + SFTP connection."""
        if self.sftp:
            return

        self.ssh_client = paramiko.SSHClient()
        self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        self.ssh_client.connect(
            hostname=self.FTP_HOST,
            port=self.FTP_PORT,
            username=self.FTP_USERNAME,
            password=self.FTP_PASSWORD,
        )

        self.sftp = self.ssh_client.open_sftp()


    def _ensure_remote_dir(self, remote_dir: Path):
        """Create remote directories recursively using SFTP."""
        remote_dir = Path(str(remote_dir).strip("/"))
        parts = remote_dir.parts

        current = ""
        for part in parts:
            current = f"{current}/{part}" if current else part

            try:
                self.sftp.stat(current)
            except FileNotFoundError:
                self.sftp.mkdir(current)

    def upload_folder(self, local_folder: Path | str, remote_folder: Path | str | None = None):
        """Upload a folder recursively, skipping files that already exist on the remote server."""
        self._init_connection()

        local_folder = Path(local_folder)
        if not local_folder.is_dir():
            raise NotADirectoryError(f"Local folder not found: {local_folder}")

        remote_folder = Path(remote_folder) if remote_folder else Path(local_folder.name)

        # Ensure the root remote folder exists
        self._ensure_remote_dir(remote_folder)

        for path in local_folder.rglob("*"):
            relative = path.relative_to(local_folder)
            remote_path = (remote_folder / relative).as_posix()

            if path.is_dir():
                # Ensure directory exists remotely
                self._ensure_remote_dir(Path(remote_path))
                continue

            # Check if remote file exists
            if self._remote_exists(remote_path):
                print(f"⏩ Skipped (already exists): {remote_path}")
                continue

            # Upload missing file
            self._ensure_remote_dir(Path(remote_path).parent)
            self.sftp.put(path.as_posix(), remote_path)
            print(f"✅ Uploaded {path} → {remote_path}")

    def _remote_exists(self, remote_path: str) -> bool:
        """Return True if a remote file exists, using SFTP.stat()."""
        try:
            self.sftp.stat(remote_path)
            return True
        except FileNotFoundError:
            return False

    def close(self):
        """Close SFTP + SSH cleanly."""
        if self.sftp:
            self.sftp.close()
            self.sftp = None

        if self.ssh_client:
            self.ssh_client.close()
            self.ssh_client = None

        print("SFTP connection closed.")


    def _delete_recursive(self, path: str):
        for item in self.sftp.listdir_attr(path):
            item_path = f"{path}/{item.filename}"

            # Directory
            if stat.S_ISDIR(item.st_mode):
                self._delete_recursive(item_path)
                self.sftp.rmdir(item_path)

            # File
            else:
                self.sftp.remove(item_path)

    def delete_remote_folder(self, remote_folder: Path | str):
        """Delete a remote folder recursively using SFTP."""
        self._init_connection()

        remote_folder = Path(remote_folder).as_posix()

        # Ensure folder exists
        try:
            self.sftp.stat(remote_folder)
        except FileNotFoundError:
            print(f"Remote folder not found: {remote_folder}")
            return
        
        self._delete_recursive(remote_folder)

        # Remove root folder
        self.sftp.rmdir(remote_folder)

        print(f"🗑️ Deleted remote folder: {remote_folder}")




if __name__ == "__main__":
    outline_volume = os.getenv("OUTLINE_VOLUME")

    # Step 1: Local backup
    backup = OutlineBackup(outline_volume)
    backup_path = backup.create_backup()

    # Step 2: Incremental upload to SFTP
    sftp = BackupHelperSFTP()

    # Always upload to the same remote folder
    remote_base = Path("home") / "outline_backups" / "current"

    sftp.upload_folder(
        local_folder=backup_path,
        remote_folder=remote_base
    )
    # sftp._init_connection()
    # sftp.sftp.chdir("./home/")
    # print(sftp.sftp.listdir())
    # sftp.delete_remote_folder(remote_base)
    sftp.close()
    backup.delete_backup()
    print("✅ Incremental backup completed.")
