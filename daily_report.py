from datetime import datetime, timedelta, timezone

from backup_logger import cleanup_logs, get_log_file, read_log_file
from discord_notifications import send_message_to_webhook


def load_last_24h():
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)

    file = get_log_file(yesterday)

    corrupted_total = 0

    entries, corrupted = read_log_file(file)
    corrupted_total += corrupted

    # Filter strictly by time window
    entries = [e for e in entries]

    return entries, corrupted_total


def analyze(entries):
    EXPECTED = 22

    total = len(entries)
    success = sum(1 for e in entries if e["status"] == "success")
    failures = total - success
    missing = EXPECTED - total

    return {
        "total": total,
        "success": success,
        "failures": failures,
        "missing": max(0, missing),
    }


def daily_report():
    entries, corrupted = load_last_24h()
    stats = analyze(entries)

    desc = (
        f"**Total:** {stats['total']}\n"
        f"✅ **Exito:** {stats['success']}\n"
        f"❌ **Fallos:** {stats['failures']}\n"
        f"⚠️ **Faltan:** {stats['missing']}\n"
        f"🧨 **Lineas corruptas (del log):** {corrupted}"
    )

    send_message_to_webhook(
        content="",
        embed_title="📊 Daily Outline Backup Report",
        embed_description=desc,
    )

    cleanup_logs()


if __name__ == "__main__":
    daily_report()
