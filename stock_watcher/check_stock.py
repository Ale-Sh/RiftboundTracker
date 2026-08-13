"""
Riftbound Restock-Watcher
Prueft die konfigurierten Shop-Seiten per HTTP-GET auf Lagerbestand-Keywords,
vergleicht mit dem letzten bekannten Status (state.json) und schickt bei
Aenderung eine Telegram-Nachricht.

Erwartet die Umgebungsvariablen TELEGRAM_BOT_TOKEN und TELEGRAM_CHAT_ID.
"""

import json
import os
import sys
import time
from datetime import datetime, timezone

import requests
import yaml

BASE_DIR = os.path.dirname(__file__)
CONFIG_PATH = os.path.join(BASE_DIR, "config.yaml")
STATE_PATH = os.path.join(BASE_DIR, "state.json")

DEFAULT_IN_STOCK = [
    "in den warenkorb", "add to cart", "auf lager",
    "sofort verfuegbar", "sofort verfügbar", "jetzt kaufen",
]
DEFAULT_OUT_OF_STOCK = [
    "ausverkauft", "sold out", "nicht auf lager",
    "nicht verfuegbar", "nicht verfügbar", "out of stock",
    "benachrichtigen", "vergriffen",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; RiftboundStockWatcher/1.0; personal use)"
}

REQUEST_TIMEOUT = 20
DELAY_BETWEEN_REQUESTS = 3


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_state():
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state):
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def send_telegram(token, chat_id, text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        r = requests.post(
            url,
            data={"chat_id": chat_id, "text": text, "disable_web_page_preview": False},
            timeout=15,
        )
        if r.status_code != 200:
            print(f"Telegram-Fehler: {r.status_code} {r.text}", file=sys.stderr)
    except requests.RequestException as e:
        print(f"Telegram-Ausnahme: {e}", file=sys.stderr)


def classify(html, shop):
    text = html.lower()
    in_kw = [k.lower() for k in shop.get("in_stock_keywords", DEFAULT_IN_STOCK)]
    out_kw = [k.lower() for k in shop.get("out_of_stock_keywords", DEFAULT_OUT_OF_STOCK)]

    has_out = any(k in text for k in out_kw)
    has_in = any(k in text for k in in_kw)

    if has_out and not has_in:
        return "bad"
    if has_in and not has_out:
        return "ok"
    return "unk"


def check_shop(shop):
    try:
        resp = requests.get(shop["url"], headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return classify(resp.text, shop)
    except requests.RequestException as e:
        print(f"Fehler bei {shop['name']}: {e}", file=sys.stderr)
        return "error"


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("TELEGRAM_BOT_TOKEN oder TELEGRAM_CHAT_ID fehlt.", file=sys.stderr)
        sys.exit(1)

    config = load_config()
    state = load_state()
    changes = []

    for shop in config["shops"]:
        shop_id = shop["id"]
        status = check_shop(shop)
        prev = state.get(shop_id, {}).get("status")
        now_iso = datetime.now(timezone.utc).isoformat()

        if status != prev:
            if status == "ok":
                changes.append(f"IN STOCK: {shop['name']}\n{shop['url']}")
            elif status == "bad" and prev == "ok":
                changes.append(f"AUSVERKAUFT (wieder): {shop['name']}\n{shop['url']}")

        state[shop_id] = {"status": status, "last_checked": now_iso, "name": shop["name"]}
        time.sleep(DELAY_BETWEEN_REQUESTS)

    save_state(state)

    if changes:
        message = "Riftbound Restock-Watcher\n\n" + "\n\n".join(changes)
        send_telegram(token, chat_id, message)
        print(f"{len(changes)} Aenderung(en) gemeldet.")
    else:
        print("Keine Statusaenderung.")


if __name__ == "__main__":
    main()
