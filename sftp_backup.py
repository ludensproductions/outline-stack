import os
import subprocess
from datetime import datetime
from ftplib import FTP, error_perm
from pathlib import Path


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
            # "sh", "-c", "ping 127.0.0.1:8080"
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


class BackupHelper:
    
    def __init__(self):
        self.FTP_SERVER = os.getenv("FTP_SERVER")
        self.FTP_PORT = int(os.getenv("FTP_PORT", "21"))
        self.FTP_USERNAME = os.getenv("FTP_USERNAME")
        self.FTP_PASSWORD = os.getenv("FTP_PASSWORD")
        self.ftp_connection = None
    
    def _init_connection(self):
        self.ftp_connection = FTP()
        self.ftp_connection.connect(
            host=self.FTP_SERVER,
            port=self.FTP_PORT,
        )
        self.ftp_connection.login(
            user=self.FTP_USERNAME,
            passwd=self.FTP_PASSWORD,
        )

    def _ensure_remote_dir(self, remote_dir: Path):
        """Create directories on the FTP server recursively if they don't exist."""
        # Normalize remote_dir (remove leading/trailing slashes)
        remote_dir = Path(str(remote_dir).strip("/"))
        parts = remote_dir.parts

        for i in range(1, len(parts) + 1):
            partial_path = "/".join(parts[:i])
            try:
                self.ftp_connection.mkd(partial_path)
            except error_perm:
                # Directory probably already exists — ignore
                pass

    def upload_file(self, local_path: Path | str, remote_path: Path | str | None = None):
        """Upload a file to the FTP server (pathlib version)."""
        self._init_connection()

        local_path = Path(local_path)
        if not local_path.is_file():
            raise FileNotFoundError(f"Local file not found: {local_path}")

        remote_path = Path(remote_path) if remote_path else Path(local_path.name)
        remote_dir = remote_path.parent

        # Create remote directory if necessary
        if str(remote_dir) not in (".", ""):
            self._ensure_remote_dir(remote_dir)

        # Upload in binary mode
        with local_path.open("rb") as file:
            self.ftp_connection.storbinary(f"STOR {remote_path.as_posix()}", file)

        print(f"✅ Uploaded {local_path} → {remote_path.as_posix()}")

    def close(self):
        """Close FTP connection safely."""
        if self.ftp_connection:
            try:
                self.ftp_connection.quit()
            except Exception:
                self.ftp_connection.close()
            finally:
                self.ftp_connection = None
                print("FTP connection closed.")


if __name__ == "__main__":
    backup = OutlineBackup(
        # "outline-stack_outline-data",
        "outline-compose_outline-data",
        Path("./backups")
    )
    backup_path = backup.create_backup()
    print(f"Backup stored at: {backup_path}")


