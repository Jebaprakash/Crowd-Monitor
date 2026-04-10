import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
COOLDOWN_SECONDS = 300

# cam_id -> last sent timestamp
_last_sent: dict[str, float] = {}


def send_telegram_alert(alert_msg: str, count: int, density: float, cam_id: str):
    """
    Send a Telegram message for the given camera.
    Enforces a 300-second cooldown per cam_id.
    Reads TELEGRAM_TOKEN and TELEGRAM_CHAT_ID from environment.
    """
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("[Telegram] Token or Chat ID not set – skipping.")
        return

    now = time.time()
    last = _last_sent.get(cam_id, 0.0)
    if now - last < COOLDOWN_SECONDS:
        remaining = COOLDOWN_SECONDS - (now - last)
        print(f"[Telegram] Cooldown active for {cam_id} ({remaining:.0f}s left).")
        return

    _last_sent[cam_id] = now

    text = (
        f"\U0001f6a8 *Crowd Alert* [{cam_id.upper()}]\n"
        f"\U0001f4cd {alert_msg}\n"
        f"\U0001f465 Count: {count}\n"
        f"\U0001f4ca Density: {density:.3f}"
    )
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        resp = requests.post(
            url,
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"},
            timeout=10,
        )
        if resp.ok:
            print(f"[Telegram] Alert sent for {cam_id}.")
        else:
            print(f"[Telegram] API error: {resp.text}")
    except Exception as e:
        print(f"[Telegram] Request failed: {e}")
