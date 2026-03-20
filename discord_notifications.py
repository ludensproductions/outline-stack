import json
import os
import traceback
from functools import wraps

import requests


def send_message_to_webhook(
    content, embed_title, embed_description="", embed_color=0x00FF00
):
    request_headers = {"Content-Type": "application/json"}

    url = os.getenv("DISCORD_BACKUP_ALERTS_URL")
    payload = {
        "content": content,
        "embeds": [
            {
                "title": embed_title,
                "description": embed_description,
                "color": embed_color,
            }
        ],
    }

    requests.post(
        url,
        headers=request_headers,
        data=json.dumps(payload),
        files=[],
    )


def notify_on_failure(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)

        except Exception as e:
            # Try to extract instance (if method)
            instance = args[0] if args else None

            # Build debug info
            error_trace = traceback.format_exc()

            context = f"**Function:** `{func.__name__}`\n"
            context += f"**Args:** {args[1:]}\n**Kwargs:** {kwargs}\n"

            # Attempt cleanup if defined
            if instance and hasattr(instance, "cleanup_on_failure"):
                try:
                    instance.cleanup_on_failure()
                except Exception as cleanup_error:
                    context += f"\nCleanup failed: {cleanup_error}\n"

            send_message_to_webhook(
                content="🚨 Backup system failure",
                embed_title=str(e),
                embed_description=f"{context}\n```{error_trace[:1500]}```",
                embed_color=0xFF0000,
            )

            raise  # NEVER swallow

    return wrapper
