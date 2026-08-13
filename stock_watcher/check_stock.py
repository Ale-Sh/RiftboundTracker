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
from bs4 import BeautifulSoup

BASE_DIR = os.path.dirname(__file__)
CONFIG_PATH = os.path.join(BASE_DIR, "config.yaml")
STATE_PATH = os.path.join(BASE_DIR, "state.json")
LEARNED_WORDS_PATH = os.path.join(BASE_DIR, "learned_booster_words.yaml")

ANNOUNCEMENTS_URL = "https://playriftbound.com/en-us/news/announcements/"
PREORDER_HINT_WORDS = ["preorder", "pre-order", "vorbestellung", "vorbestellen"]

# Produkte mit zufaelligem Boosterinhalt (Displays, Tins, Elite Trainer Boxen ...).
# Champion-Decks, Sleeves, Playmats usw. haben festgelegten Inhalt und zaehlen NICHT dazu.
BOOSTER_PRODUCT_WORDS = [
    "display", "booster box", "booster display", "tin",
    "elite trainer box", " etb", "trainer box", "booster pack", "bundle",
]

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
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "de-AT,de;q=0.9,en;q=0.8",
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


def load_learned_words():
    if os.path.exists(LEARNED_WORDS_PATH):
        with open(LEARNED_WORDS_PATH, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or []
            return [str(w).lower() for w in data]
    return []


def save_learned_words(words):
    with open(LEARNED_WORDS_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(sorted(set(words)), f, allow_unicode=True)


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
            return None
        return r.json().get("result", {}).get("message_id")
    except requests.RequestException as e:
        print(f"Telegram-Ausnahme: {e}", file=sys.stderr)
        return None


def get_telegram_updates(token, offset):
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    params = {"timeout": 0}
    if offset is not None:
        params["offset"] = offset
    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        return r.json().get("result", [])
    except requests.RequestException as e:
        print(f"Telegram-Updates-Fehler: {e}", file=sys.stderr)
        return []


def process_telegram_replies(token, chat_id, state):
    """Liest Antworten auf offene Rueckfragen (state['pending_questions'])
    und lernt daraus neue Booster-Produkt-Schlagworte."""
    pending = state.get("pending_questions", {})
    last_update_id = state.get("last_update_id")
    offset = (last_update_id + 1) if last_update_id is not None else None
    updates = get_telegram_updates(token, offset)

    if not updates:
        return

    learned = set(load_learned_words())
    max_update_id = last_update_id or 0

    for update in updates:
        max_update_id = max(max_update_id, update.get("update_id", 0))
        message = update.get("message")
        if not message:
            continue
        reply_to = message.get("reply_to_message")
        if not reply_to:
            continue
        replied_id = str(reply_to.get("message_id"))
        if replied_id not in pending:
            continue

        answer = (message.get("text") or "").strip().lower()
        pending.pop(replied_id)

        if answer in ("nein", "no", "n"):
            send_telegram(token, chat_id, "Ok, notiert - kein Boosterprodukt.")
        elif answer:
            learned.add(answer)
            send_telegram(
                token, chat_id,
                f"Danke! '{answer}' wird jetzt als Hinweis auf ein Display/Booster-Produkt genutzt."
            )

    state["pending_questions"] = pending
    state["last_update_id"] = max_update_id
    save_learned_words(learned)


def classify(html, shop):
    text = html.lower()
    in_kw = [k.lower() for k in shop.get("in_stock_keywords", DEFAULT_IN_STOCK)]
    out_kw = [k.lower() for k in shop.get("out_of_stock_keywords", DEFAULT_OUT_OF_STOCK)]
    has_out = any(k in text for k in out_kw)

    if not in_kw:
        # Absenz-Modus (z. B. Preisvergleichsseiten wie Geizhals): kein
        # "in Lager"-Wort noetig, es reicht, dass der "keine Anbieter"-Satz fehlt.
        return "bad" if has_out else "ok"

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


def check_announcements(state, token, chat_id):
    """Prueft die offizielle Riftbound-News-Seite auf neue Eintraege, deren
    Titel auf eine Vorbestellung hindeuten. Anders als bei den Shops wird
    beim allerersten Lauf nichts gemeldet, sondern nur der aktuelle Stand
    gespeichert, damit nicht sofort alte Artikel als "neu" durchgehen."""
    changes = []
    try:
        resp = requests.get(ANNOUNCEMENTS_URL, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"Fehler beim Abrufen der Riftbound-News: {e}", file=sys.stderr)
        return changes

    first_run = "seen_announcements" not in state
    seen = set(state.get("seen_announcements", []))
    booster_words = BOOSTER_PRODUCT_WORDS + load_learned_words()
    pending = state.setdefault("pending_questions", {})

    soup = BeautifulSoup(resp.text, "html.parser")
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/news/announcements/" not in href or href.rstrip("/").endswith("/announcements"):
            continue
        title_text = a.get_text(" ", strip=True)
        if not title_text:
            continue
        full_url = href if href.startswith("http") else "https://playriftbound.com" + href

        if full_url in seen:
            continue
        seen.add(full_url)

        if not first_run:
            lower = title_text.lower()
            is_preorder = any(w in lower for w in PREORDER_HINT_WORDS)
            is_booster_product = any(w in lower for w in booster_words)
            if is_preorder and is_booster_product:
                changes.append(f"VORBESTELLUNG (Display/Booster-Produkt): {title_text}\n{full_url}")
            elif is_preorder:
                question = (
                    f"VORBESTELLUNG, Produkttyp unklar: {title_text}\n{full_url}\n\n"
                    "Antworte auf DIESE Nachricht (Telegram-Antwortfunktion) mit einem "
                    "Begriff aus dem Titel, der Boosterprodukte kennzeichnet (z. B. "
                    "'display' oder 'tin'), damit ich das kuenftig automatisch erkenne. "
                    "Ist es KEIN Boosterprodukt (z. B. einzelnes Deck), antworte mit 'nein'."
                )
                msg_id = send_telegram(token, chat_id, question)
                if msg_id:
                    pending[str(msg_id)] = {"url": full_url, "title": title_text}
            else:
                changes.append(f"Neuer Riftbound-News-Artikel: {title_text}\n{full_url}")

    state["seen_announcements"] = list(seen)[-200:]
    return changes


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("TELEGRAM_BOT_TOKEN oder TELEGRAM_CHAT_ID fehlt.", file=sys.stderr)
        sys.exit(1)

    config = load_config()
    state = load_state()
    changes = []

    process_telegram_replies(token, chat_id, state)

    for shop in config["shops"]:
        shop_id = shop["id"]
        status = check_shop(shop)
        prev = state.get(shop_id, {}).get("status")
        now_iso = datetime.now(timezone.utc).isoformat()
        is_fixed_content = shop.get("product_type") == "fixed"

        if status != prev and not is_fixed_content:
            if status == "ok":
                changes.append(f"IN STOCK: {shop['name']}\n{shop['url']}")
            elif status == "bad" and prev == "ok":
                changes.append(f"AUSVERKAUFT (wieder): {shop['name']}\n{shop['url']}")

        state[shop_id] = {"status": status, "last_checked": now_iso, "name": shop["name"]}
        time.sleep(DELAY_BETWEEN_REQUESTS)

    changes.extend(check_announcements(state, token, chat_id))

    save_state(state)

    if changes:
        message = "Riftbound Restock-Watcher\n\n" + "\n\n".join(changes)
        send_telegram(token, chat_id, message)
        print(f"{len(changes)} Aenderung(en) gemeldet.")
    else:
        print("Keine Statusaenderung.")


if __name__ == "__main__":
    main()
