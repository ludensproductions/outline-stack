import os
from pathlib import Path


import paramiko
from dotenv import load_dotenv


load_dotenv()


class BackupHelperSFTP:

    def __init__(self, retention_limit: int = 10):
        self.FTP_HOST = os.getenv("FTP_HOST")
        self.FTP_PORT = int(os.getenv("FTP_PORT", "22"))
        self.FTP_USERNAME = os.getenv("FTP_USERNAME")
        self.FTP_PASSWORD = os.getenv("FTP_PASSWORD")

        self.retention_limit = retention_limit

        self.ssh_client = None
        self.sftp = None

    def _init_connection(self):
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
        remote_dir = Path(str(remote_dir).strip("/"))
        current = ""

        for part in remote_dir.parts:
            current = f"{current}/{part}" if current else part
            try:
                self.sftp.stat(current)
            except FileNotFoundError:
                self.sftp.mkdir(current)

    def upload_backup(
        self,
        local_archive: Path | str,
        remote_dir: Path | str,
    ):
        """
        Upload a single backup archive and enforce retention.

        Arguments:
            local_archive (Path | str): Path to the local backup archive.
            remote_dir (Path | str): Path to the remote backup directory.
        """
        self._init_connection()

        local_archive = Path(local_archive)
        if not local_archive.is_file():
            raise FileNotFoundError(local_archive)

        remote_dir = Path(remote_dir)
        self._ensure_remote_dir(remote_dir)

        remote_path = (remote_dir / local_archive.name).as_posix()

        # Do not overwrite backups silently
        try:
            self.sftp.stat(remote_path)
            raise RuntimeError(f"Remote backup already exists: {remote_path}")
        except FileNotFoundError:
            pass

        print(f"Uploading backup: {local_archive.name}")
        self.sftp.put(local_archive.as_posix(), remote_path)

        self._enforce_retention(remote_dir)

    def _enforce_retention(self, remote_dir: Path):
        """
        Keep only the newest N backups in the remote directory.

        Arguments:
            remote_dir (Path): Path to the remote directory containing backups.
        """

        files = self.sftp.listdir_attr(remote_dir.as_posix())
        files.sort(key=lambda x: x.st_mtime, reverse=True)
    
        if len(files) <= self.retention_limit:
            return

        # Get the oldest files to delete it
        for file_attr in files[self.retention_limit:]:
            file_path = (remote_dir / file_attr.filename).as_posix()
            print(f"Deleting old backup: {file_attr.filename}")
            self.sftp.remove(file_path)

    def download_backup(
        self,
        remote_dir: Path | str,
        local_dir: Path | str,
    ):
        """
        Download the latest backup archive from the remote directory.
        Arguments:
            remote_dir (Path | str): Path to the remote backup directory.
            local_dir (Path | str): Local directory to save the downloaded archive.

        Returns:
            Path: The local path to the downloaded backup archive.
        """
        self._init_connection()

        remote_archive = self._get_latest_backup(remote_dir)
        local_dir = Path(local_dir)
        local_dir.mkdir(parents=True, exist_ok=True)

        local_path = local_dir / remote_archive.name

        print(f"Downloading backup: {remote_archive.name}")
        self.sftp.get(remote_archive.as_posix(), local_path.as_posix())

        return local_path

    def _get_latest_backup(self, remote_dir: Path | str) -> Path:
        remote_dir = Path(remote_dir)
        files = self.sftp.listdir_attr(remote_dir.as_posix())
        if not files:
            raise FileNotFoundError(f"No backups found in remote directory: {remote_dir}")

        # Sort by modification time descending
        files.sort(key=lambda x: x.st_mtime, reverse=True)
        latest_file = files[0]
        return remote_dir / latest_file.filename

    def close(self):
        if self.sftp:
            self.sftp.close()
            self.sftp = None
        if self.ssh_client:
            self.ssh_client.close()
            self.ssh_client = None

