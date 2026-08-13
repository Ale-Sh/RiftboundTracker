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

## 6. Mehr Haendler abdecken ueber Geizhals (Preisvergleich)

Statt jeden einzelnen Shop von Hand einzutragen, gibt es einen Umweg, der
automatisch viele Haendler auf einmal abdeckt: **Geizhals.de** ist ein
Preisvergleichsdienst, der auf einer einzigen Produktseite alle Angebote
verschiedener Haendler zusammenfasst. Ist ein Produkt nirgends verfuegbar,
steht dort woertlich "Es gibt derzeit keine Anbieter fuer dieses Produkt".
Sobald irgendein erfasster Haendler es listet, verschwindet dieser Satz.

In `config.yaml` sind aktuell zwei Geizhals-Produktseiten eingetragen
(Origins Booster Display, Spiritforged Booster Display). Fuer neuere Sets
(z. B. Unleashed, Vendetta) habe ich keine zuverlaessige Geizhals-Seite
gefunden - Riftbound bringt haeufig neue Sets raus, und Geizhals listet sie
nicht immer sofort. So findest und ergaenzt du sie selbst:

1. Auf geizhals.de nach "riftbound [setname] booster display" suchen
   (z. B. "riftbound vendetta booster display")
2. Die Produktseite oeffnen, URL kopieren
3. In `config.yaml` einen neuen Block nach dem Muster der bestehenden
   Geizhals-Eintraege ergaenzen:

```yaml
  - id: geizhals_vendetta_display
    name: "Geizhals - Vendetta Booster Display"
    category: "Preisvergleich (Geizhals, viele Haendler)"
    url: "https://geizhals.de/DIE-KOPIERTE-URL-HIER.html"
    in_stock_keywords: []
    out_of_stock_keywords: ["es gibt derzeit keine anbieter"]
    product_type: booster
```

**Wichtig:** Geizhals blockt bei zu haeufigen automatischen Zugriffen
kurzzeitig mit einer Fehlermeldung (HTTP 429 "zu viele Anfragen"). Bei einem
Check alle 20 Minuten sollte das kaum vorkommen; falls doch, im Actions-Log
nachsehen, ob `geizhals_...` als `error` markiert wird, und im Zweifel das
Intervall in `watch.yml` auf 30 Minuten erhoehen.

**Alternative ganz ohne eigenes Skript:** Geizhals hat einen eingebauten
**Preisalarm** (Button "Preisalarm setzen" auf jeder Produktseite). Trägst du
dort deine Preisobergrenze ein, bekommst du automatisch eine E-Mail, sobald
irgendein Haendler das Produkt zu diesem Preis oder guenstiger listet — das
deckt implizit auch "wieder verfuegbar" ab, weil aktuell ja niemand listet.
Nachteil: E-Mail statt Telegram, dafuer in 2 Minuten eingerichtet und ohne
GitHub. Praktisch als Rueckversicherung parallel zum eigenen Watcher.

## 7. Vorbestellungen beim offiziellen Riot Store

Der Riot Games Store selbst laedt seine Produktseiten per JavaScript nach –
ein einfacher automatischer Seitenabruf sieht dort praktisch nichts
Brauchbares (deshalb `unreliable: true`). Riot kuendigt neue Vorbestellungen
aber vorher schriftlich in einem News-Blog an, und diese Seite ist normal
auslesbar:

https://playriftbound.com/en-us/news/announcements/

`check_stock.py` prueft diese Seite bei jedem Lauf zusaetzlich zu den Shops.
Taucht dort ein neuer Artikel auf, kommt eine eigene Telegram-Nachricht mit
Titel und Link. Artikel, deren Titel "preorder", "pre-order",
"vorbestellung" oder "vorbestellen" enthaelt, werden dabei extra als
VORBESTELLUNG markiert, damit du sie sofort erkennst. Nichts an
`config.yaml` muss dafuer angepasst werden, das laeuft automatisch mit.

**Wichtig zu wissen:** Riot hat das Vorbestell-Verfahren umgestellt. Es ist
kein "wer zuerst im Shop ist, bekommt es"-Rennen mehr, sondern ein
**Losverfahren**: Man traegt sich in einem 48-Stunden-Fenster ein, wird
zufaellig gezogen (oder nicht), und bekommt bei Erfolg einen Kauflink per
E-Mail. Die Telegram-Nachricht von unserem Watcher sagt dir also: "jetzt ist
das Anmeldefenster fuer eine Vorbestellung offen" – nicht "jetzt sofort
kaufen". Zeitdruck besteht trotzdem, weil das Anmeldefenster nur 48 Stunden
offen ist.

## 8. Nur Displays/Tins/Boosterware statt allem

Standardmaessig zaehlen als "interessant" alle Produkte mit **zufaelligem**
Boosterinhalt: Displays, Booster-Boxen, Tins, Elite Trainer Boxen (falls
Riftbound sowas anbietet), Bundles. Einzelne Champion-Decks, Sleeves,
Playmats & Co. haben festen Inhalt und sollen NICHT benachrichtigen.

**Bei Shops/Geizhals-Seiten** (`config.yaml`): Jeder Eintrag kann
`product_type: fixed` bekommen. Der Shop wird weiter geprueft (taucht also
im Ledger-Sync korrekt auf), loest aber keine Telegram-Nachricht mehr aus.
Ohne dieses Feld (oder mit `product_type: booster`) wird ganz normal
benachrichtigt. Aktuell ist nur `geizhals_leesin_deck` als `fixed` markiert,
weitere Champion-Deck-Seiten sollten beim Eintragen genauso markiert werden.

**Bei den Riot-News-Artikeln**: Der Titel wird zusaetzlich nach Woertern wie
"display", "tin", "elite trainer box", "booster box" durchsucht
(`BOOSTER_PRODUCT_WORDS` oben in `check_stock.py`). Ein Vorbestell-Artikel
wird dann so gekennzeichnet:

- **VORBESTELLUNG (Display/Booster-Produkt)** – Titel enthaelt sowohl ein
  Vorbestell- als auch ein Booster-Wort, hoechste Prioritaet
- **VORBESTELLUNG (Produkttyp unklar, bitte pruefen)** – Titel deutet auf
  eine Vorbestellung hin, aber nicht klar erkennbar ob Display oder Deck
  (z. B. wenn der Artikeltitel selbst keine Produktnamen enthaelt) – hier
  lohnt sich ein Blick auf den verlinkten Artikel
- **Neuer Riftbound-News-Artikel** – alles andere, weiterhin gemeldet, aber
  ohne Vorbestell-Bezug

Da Riftbound noch neue Produktkategorien einfuehren kann, die diese
Wortliste nicht abdeckt, lieber ab und zu einen Blick auf "Produkttyp
unklar"-Nachrichten werfen und bei Bedarf `BOOSTER_PRODUCT_WORDS` ergaenzen.

## 9. Der Bot lernt aus deinen Antworten

Wenn ein News-Artikel eine Vorbestellung ankuendigt, aber unklar ist, ob es
ein Boosterprodukt ist, schickt der Bot dir eine eigene Nachricht mit einer
Rueckfrage. So antwortest du:

1. In Telegram auf genau diese Nachricht mit der **Antworten**-Funktion
   reagieren (nicht einfach eine neue Nachricht schreiben — der Bot erkennt
   nur "Antworten auf diese Nachricht" als gueltige Reaktion)
2. Entweder einen Begriff aus dem Titel eintippen, der Boosterprodukte
   kennzeichnet (z. B. "tin" oder "elite trainer box")
3. Oder "nein" schreiben, falls es kein Boosterprodukt ist (z. B. ein
   einzelnes Deck)

Beim naechsten automatischen Lauf (max. 20 Minuten spaeter) liest das
Programm deine Antwort, speichert den Begriff in
`stock_watcher/learned_booster_words.yaml` (wird automatisch ins Repo
committet) und bestaetigt dir das per Telegram. Ab dann werden Artikel mit
diesem Begriff automatisch richtig eingeordnet, ohne erneut zu fragen.

**Achtung, kleine Falle:** Antwortest du nicht ueber die
Telegram-Antworten-Funktion, sondern schickst einfach eine normale neue
Nachricht, kann der Bot sie keiner Frage zuordnen und ignoriert sie
stillschweigend. Falls eine Antwort nicht ankommt, zuerst pruefen, ob wirklich
auf die Bot-Nachricht geantwortet wurde.

## Naechste Schritte / Ausbau

- Preisobergrenze direkt im Skript pruefen, sobald ein Shop den Preis im
  HTML sichtbar auflistet (dafuer bräuchte man einen shop-spezifischen
  Preis-Selektor – gerne bei Bedarf ergaenzen).
- Mehrere Chat-IDs / eine Telegram-Gruppe statt Einzelchat.
- Cron-Intervall in `watch.yml` anpassen (z. B. `*/10 * * * *` für alle 10 Min).
