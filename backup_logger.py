import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

LOG_DIR = Path("./logs")
LOG_DIR.mkdir(exist_ok=True)
LOCAL_TZ = ZoneInfo("America/Hermosillo")  # Sonora = no DST


def get_log_file(ts_utc: datetime) -> Path:
    local_ts = ts_utc.astimezone(LOCAL_TZ)
    return LOG_DIR / f"{local_ts.strftime('%Y-%m-%d')}.jsonl"


def cleanup_logs(days=7):
    cutoff = datetime.now(LOCAL_TZ) - timedelta(days=days)

    for file in LOG_DIR.glob("*.jsonl"):
        date_str = file.stem
        file_date = datetime.strptime(date_str, "%Y-%m-%d").astimezone(LOCAL_TZ)

        if file_date < cutoff:
            file.unlink(missing_ok=True)


def log_execution(entry: dict):
    """
    Append one JSON line safely.
    """
    ts = datetime.fromtimestamp(entry["timestamp"])
    log_file = get_log_file(ts)

    line = json.dumps(entry, separators=(",", ":"))

    # Critical: open in append mode + flush + fsync
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(line + "\n")
        f.flush()
        os.fsync(f.fileno())


def build_log_entry(start_time: datetime, status: str, duration: float, error=None):
    return {
        "timestamp": start_time.timestamp(),
        "status": status,  # "success" | "failure"
        "duration": round(duration, 3),
        "error": error,
    }


def read_log_file(path: Path):
    entries = []
    corrupted = 0

    if not path.exists():
        return entries, corrupted

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                corrupted += 1

    return entries, corrupted
