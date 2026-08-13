# Riftbound Restock-Watcher (GitHub Actions + Telegram)

Prueft alle 20 Minuten die konfigurierten Shops und schickt dir eine
Telegram-Nachricht, sobald sich der Lagerstatus aendert.

## 0. Kombination mit dem Ledger-Tool

Das separate Ledger (HTML-Artefakt) kann die `state.json` dieses Watchers
direkt einlesen ("Jetzt synchronisieren"-Button dort). Dafuer muss das Repo
**oeffentlich** sein, damit die Raw-URL ohne Login erreichbar ist:

```
https://raw.githubusercontent.com/<dein-user>/riftbound-watcher/main/stock_watcher/state.json
```

Diese Datei enthaelt nur Shopnamen, URLs und Lagerstatus – nichts
Sensibles. Der Telegram-Bot-Token bleibt trotzdem sicher, weil er als
GitHub Secret gespeichert ist und nie in eine Datei im Repo geschrieben wird.

Wenn dir ein oeffentliches Repo nicht zusagt: Watcher funktioniert auch
ohne Ledger-Sync einwandfrei, dann einfach Schritt 1 mit "privat" wie
gehabt.

## 1. Repo anlegen

1. Neues GitHub-Repo erstellen (z. B. `riftbound-watcher`) – **oeffentlich**,
   falls du den Ledger-Sync aus Schritt 0 nutzen willst, sonst privat.
2. Diese Dateien/Ordner in das Repo pushen:
   - `stock_watcher/config.yaml`
   - `stock_watcher/check_stock.py`
   - `stock_watcher/state.json`
   - `requirements.txt`
   - `.github/workflows/watch.yml`

```bash
cd riftbound-watcher
git init
git add .
git commit -m "init"
git branch -M main
git remote add origin https://github.com/<dein-user>/riftbound-watcher.git
git push -u origin main
```

Privates Repo, weil `state.json` und Logs sonst oeffentlich einsehbar sind –
inhaltlich unproblematisch, aber unnoetig.

## 2. Telegram-Bot erstellen

1. In Telegram den Bot **@BotFather** oeffnen, `/newbot` senden, Namen vergeben.
2. BotFather gibt dir einen **Bot-Token** (Format `123456789:ABC...`) – notieren.
3. Deinem neuen Bot eine beliebige Nachricht schicken (z. B. "hi"), damit er
   deinen Chat kennt.
4. Deine **Chat-ID** herausfinden: im Browser
   `https://api.telegram.org/bot<DEIN_TOKEN>/getUpdates` aufrufen, nachdem du
   dem Bot geschrieben hast. Im JSON steht `"chat":{"id": 123456789, ...}`.
   Alternativ den Bot **@userinfobot** nach deiner ID fragen.

## 3. Secrets im Repo hinterlegen

GitHub-Repo → **Settings → Secrets and variables → Actions → New repository secret**

| Name | Wert |
|---|---|
| `TELEGRAM_BOT_TOKEN` | der Bot-Token aus Schritt 2 |
| `TELEGRAM_CHAT_ID` | deine Chat-ID aus Schritt 2 |

## 4. Actions aktivieren

Im Repo unter **Actions** den Workflow **"Riftbound Stock Watcher"** einmal
manuell ueber **"Run workflow"** starten, um zu testen. Danach laeuft er von
selbst alle 20 Minuten (`cron: */20 * * * *` in `watch.yml`).

## 5. Shops anpassen

Alles in `stock_watcher/config.yaml`:

```yaml
shops:
  - id: amzicards
    name: "Amzicards.de"
    category: "Fachshops (DE)"
    url: "https://amzicards.de/produkt-seite-hier"
```

Am besten die konkrete **Produktseite** des Displays eintragen, nicht die
Startseite – dort stehen die eindeutigen Lager-Keywords ("Ausverkauft",
"In den Warenkorb" etc.), sobald das Set gelistet ist.

Eigene Keywords pro Shop (falls Standardwoerter nicht passen):

```yaml
  - id: mein_shop
    name: "Mein Shop"
    url: "https://..."
    in_stock_keywords: ["jetzt bestellen", "verfuegbar"]
    out_of_stock_keywords: ["restock", "vorbestellung ausverkauft"]
```

## Wichtige Einschraenkungen

- **JavaScript-lastige Seiten und Bot-Schutz**: Amazon, Cardmarket und der
  Riot Games Store laden Inhalte teils per JavaScript nach oder blockieren
  einfache Skript-Zugriffe. Der simple Keyword-Check in `config.yaml` hat
  sie deshalb mit `unreliable: true` markiert – die Erkennung kann dort
  falsch liegen oder ganz ausbleiben. Fuer diese drei bleibt manuelles
  Pruefen (z. B. ueber das Ledger-Tool) zuverlaessiger.
- **Kein Ersatz fuer Nutzungsbedingungen**: Automatisiertes Abrufen von
  Shop-Seiten kann gegen die AGB einzelner Anbieter verstossen. Ein
  Intervall von 15–20 Minuten mit normalem User-Agent ist fuer den
  persoenlichen Gebrauch unauffaellig, aber im Zweifel die AGB des
  jeweiligen Shops pruefen.
- **GitHub Actions Scheduling ist nicht exakt**: Bei hoher Auslastung kann
  ein geplanter Lauf ein paar Minuten spaeter starten – für Restock-Alerts
  meist unerheblich.
- **Kosten**: In privaten Repos sind GitHub-Actions-Minuten begrenzt (Free
  Tier: 2000 Min/Monat). Ein Lauf alle 20 Minuten braucht ca. 1–2 Minuten
  Laufzeit → passt locker ins Freikontingent.

## Naechste Schritte / Ausbau

- Preisobergrenze direkt im Skript pruefen, sobald ein Shop den Preis im
  HTML sichtbar auflistet (dafuer bräuchte man einen shop-spezifischen
  Preis-Selektor – gerne bei Bedarf ergaenzen).
- Mehrere Chat-IDs / eine Telegram-Gruppe statt Einzelchat.
- Cron-Intervall in `watch.yml` anpassen (z. B. `*/10 * * * *` für alle 10 Min).
