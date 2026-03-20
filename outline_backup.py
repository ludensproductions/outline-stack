import os
import platform
import shutil
import stat
import subprocess
import tarfile
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from dotenv import load_dotenv

from discord_notifications import notify_on_failure

load_dotenv()


class OutlineBackup:
    def __init__(
        self,
        outline_volume: str,
        restore_archive_path: Path | str | None = None,
        backup_root: Path | str = Path("./backups"),
    ):
        self.outline_volume = outline_volume
        self.backup_root = Path(backup_root).resolve()
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        self.SQL_USER = os.getenv("SQL_USER")
        self.SQL_DBNAME = os.getenv("SQL_DBNAME")

        self.work_dir = self.backup_root / f"{outline_volume}_{self.timestamp}"
        self.archive_path = (
            self.backup_root / f"{outline_volume}_{self.timestamp}.tar.gz"
        )

        # Restore variable
        self.restore_archive_path = restore_archive_path

    def cleanup_on_failure(self):
        print("Running cleanup...")

        if self.work_dir.exists():
            shutil.rmtree(self.work_dir, ignore_errors=True)

        if self.restore_archive_path is not None:
            archive_path = Path(self.restore_archive_path)
            archive_path.unlink(missing_ok=True)

    def _run(self, cmd: list[str], **kwargs):
        if platform.system() != "Windows":
            cmd = ["sudo"] + cmd

        result = subprocess.run(cmd, capture_output=True, text=True, **kwargs)

        if result.returncode != 0:
            raise RuntimeError(f"Command failed:\n{' '.join(cmd)}\n\n{result.stderr}")

        return result

    def _dump_db(self, dump_path: Path):
        print("Dumping database...")

        cmd = [
            "docker",
            "compose",
            "exec",
            "-T",
            "postgres",
            "pg_dump",
            "-U",
            self.SQL_USER,
            "-d",
            self.SQL_DBNAME,
            "-F",
            "c",
            "-Z",
            "9",
        ]

        with open(dump_path, "wb") as f:
            result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE)

        if result.returncode != 0:
            raise RuntimeError(f"DB dump failed:\n{result.stderr.decode()}")

        if dump_path.stat().st_size == 0:
            raise RuntimeError("DB dump is empty (silent failure)")

    def _copy_volume(self):
        print(f"Copying volume: {self.outline_volume}")

        cmd = [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{self.outline_volume}:/volume-data:ro",
            "-v",
            f"{self.work_dir}:/backup-data",
            "busybox",
            "sh",
            "-c",
            "cp -r /volume-data/* /backup-data/ 2>/dev/null || true",
        ]

        self._run(cmd)

    @notify_on_failure
    def create_backup(self) -> Path:
        self.work_dir.mkdir(parents=True, exist_ok=True)

        dump_path = self.work_dir / "outline_db.dump"

        # 1. Dump DB
        self._dump_db(dump_path)

        # 2. Copy media volume
        self._copy_volume()

        # 3. Create archive (single pass)
        print(f"Creating archive: {self.archive_path}")

        with tarfile.open(self.archive_path, "w:gz") as tar:
            for item in self.work_dir.iterdir():
                if item.name == "outline_db.dump":
                    tar.add(item, arcname="db/outline_db.dump")
                else:
                    tar.add(item, arcname=f"media/{item.name}")

        # 4. Cleanup (handle docker permission garbage)
        def _on_rm_error(func, path, exc_info):
            try:
                os.chmod(path, stat.S_IWUSR)
                func(path)
            except Exception:
                pass

        shutil.rmtree(self.work_dir, onerror=_on_rm_error)

        print("Backup created successfully.")
        return self.archive_path

    def _restore_volume(self, media_dir: Path):
        print("Restoring media volume (clean overwrite)...")
        media_cmd = [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{self.outline_volume}:/volume-data",
            "-v",
            f"{media_dir}:/restore-data:ro",
            "busybox",
            "sh",
            "-c",
            # Clean + copy
            "rm -rf /volume-data/* && cp -r /restore-data/* /volume-data/",
        ]

        self._run(media_cmd)

    def _restore_db(self, db_dump: Path):
        print("Restoring database...")

        db_cmd = [
            "docker",
            "compose",
            "exec",
            "-T",
            "postgres",
            "pg_restore",
            "-U",
            self.SQL_USER,
            "-d",
            self.SQL_DBNAME,
            "--clean",  # drop existing objects
            "--if-exists",
        ]

        with open(db_dump, "rb") as f:
            result = subprocess.run(db_cmd, stdin=f, stderr=subprocess.PIPE)

        if result.returncode != 0:
            raise RuntimeError(f"DB restore failed:\n{result.stderr.decode()}")

    @notify_on_failure
    def restore_backup(self):
        archive_path = Path(self.restore_archive_path)
        if not archive_path.is_file():
            raise FileNotFoundError(archive_path)

        with TemporaryDirectory(prefix="restore_") as tmp:
            temp_dir = Path(tmp)

            print(f"Extracting backup from {archive_path}")
            with tarfile.open(archive_path, "r:gz") as tar:
                tar.extractall(path=temp_dir)

            media_dir = temp_dir / "media"
            db_dump = temp_dir / "db" / "outline_db.dump"

            if not media_dir.exists():
                raise RuntimeError("Missing media directory in backup")

            if not db_dump.exists():
                raise RuntimeError("Missing database dump in backup")

            # --- 1. Restore media (clean volume first) ---
            self._restore_volume(media_dir=media_dir)

            # --- 2. Restore database ---
            self._restore_db(db_dump=db_dump)

            print("Restore completed successfully.")
