"""Alert channel. Telegram if configured, always logged to state/alerts.json.
Usage: python alert.py "TYPE" "message text"  (or import send_alert)."""
import sys
import time

import requests

from psx_data import STATE, load_config, load_json, save_json


def send_alert(kind: str, text: str) -> bool:
    cfg = load_config()["alerts"]
    log = load_json(STATE / "alerts.json", [])
    entry = {"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "type": kind, "text": text, "delivered": False}

    token, chat = cfg.get("telegram_bot_token"), cfg.get("telegram_chat_id")
    if token and chat:
        try:
            r = requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat, "text": f"[{kind}] {text}"},
                timeout=15,
            )
            entry["delivered"] = r.status_code == 200
        except requests.RequestException as e:
            entry["error"] = str(e)[:120]

    log.append(entry)
    save_json(STATE / "alerts.json", log[-500:])
    return entry["delivered"]


if __name__ == "__main__":
    kind = sys.argv[1] if len(sys.argv) > 1 else "INFO"
    text = sys.argv[2] if len(sys.argv) > 2 else ""
    ok = send_alert(kind, text)
    print(f"alert logged{' + telegram delivered' if ok else ' (telegram not configured/failed)'}")
