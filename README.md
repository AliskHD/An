# Mont Blanc Tagesplanung

Automatisiert den taeglichen Ablauf in der Mont Blanc Abteilung:

1. **Teams-Bot** (Bot Framework + Adaptive Cards) nimmt Tagesmeldungen der
   Mitarbeiter entgegen – primaer als strukturierte Karte, wahlweise auch als
   Freitext (den Claude fuer uns parst, bei Unklarheit kommt eine Rueckfrage-Karte
   mit Vorbelegung zurueck).
2. **Orchestrator** liest abends alle Meldungen, schreibt die Losstaende fort
   und erzeugt den Tagesplan fuer morgen.
3. Der Tagesplan landet als **Adaptive Card** im Teams-Chat und zusaetzlich als
   **Excel-Archiv** im `output/`-Ordner.

## Datenfluss

```
   Mitarbeiter in Teams
   │
   │ (1) Adaptive-Card-Submit  ──► Bot (Messaging-Endpoint /api/messages)
   │                                 │
   │ (2) Freitext  ────────────────► Bot ──► Claude (messages.parse) ──► Karte zurueck
                                     │
                                     ▼
                               state/meldungen/*.json
                                     │
                                     ▼ (abends: montblanc tagesablauf)
                 data/*.md + stammdaten.yaml ─► Planer ─► Excel + Tagesplan-Karte
                                                              │
                                                              ▼
                                                 proaktiv an alle ConversationRefs
```

## Daten

Alle Stammdaten liegen als Markdown / YAML unter `data/`:

| Datei                         | Inhalt                                          |
|-------------------------------|-------------------------------------------------|
| `losstaende.md`               | Aktive Lose mit Menge, Schritt, Prioritaet      |
| `qualifikationsmatrix.md`     | Mitarbeiter x Prozessschritt, Qualifikation 0-3 |
| `stammdaten.yaml`             | Prozessschritte (Dauer/Stueck, Min-Quali), Schicht |

Laufzeit-State liegt in `state/`:
- `conversation_refs.json` – pro Mitarbeiter der Teams-Kanal zum proaktiven Antworten
- `meldungen/tagesmeldungen_<DATUM>.json` – was der Bot heute eingesammelt hat

## Installation

```bash
pip install -e .
cp .env.example .env      # dann Secrets eintragen
```

## Benutzung

**Bot starten** (Messaging-Endpoint fuer Teams):

```bash
montblanc bot serve
# laeuft auf http://0.0.0.0:3978/api/messages
```

**Tagesmeldungs-Aufforderung** an alle Mitarbeiter, die schon mal mit dem Bot
geschrieben haben:

```bash
montblanc bot prompt-tagesmeldung
```

**Tagesablauf am Abend** (Plan fuer morgen, Excel, Teams-Post):

```bash
montblanc tagesablauf --tag 2026-04-21
```

**Nur Planung** (keine Teams-Interaktion, aus den .md-Dateien):

```bash
montblanc nur-plan --datum 2026-04-22
```

## Azure-Bot-Setup (einmalig)

Die Credentials gehoeren zu *eurer* Azure-AD-App-Registration – niemals meine
und niemals frei erfunden. Schritt fuer Schritt:

1. **App-Registration** – Azure-Portal -> *Entra ID* -> *App-Registrierungen* ->
   die bestehende Claude-App auswaehlen (oder neu anlegen). Aus *Uebersicht*
   ins `.env` uebernehmen:
   - `MICROSOFT_APP_ID`      = Anwendungs-ID (Client)
   - `MICROSOFT_APP_TENANT_ID` = Verzeichnis-ID (Tenant)
2. **Client-Secret** – in derselben App -> *Zertifikate & Geheimnisse* ->
   *Neuer geheimer Clientschluessel*. Den Wert (nicht die ID!) in
   `MICROSOFT_APP_PASSWORD` eintragen.
3. **Bot-Ressource** – Azure-Portal -> *Azure Bot* -> die Ressource, die zur
   App gehoert. Unter *Configuration* den **Messaging endpoint** setzen:
   - lokal mit Tunnel: `https://<dein-ngrok-subdomain>.ngrok-free.app/api/messages`
   - hosted: die oeffentliche URL eures Prozesses + `/api/messages`
4. **Teams-Channel aktivieren** – Bot-Ressource -> *Channels* -> *Microsoft Teams*
   hinzufuegen (falls nicht schon aktiv). Bei bestehendem Claude-cowork-Bot
   ist dieser Channel schon konfiguriert.
5. **Manifest / Installation** – wenn der Bot in eurem Teams bereits installiert
   ist (Claude cowork), bleibt der User-Eintrag erhalten; nur der Messaging-
   Endpoint zeigt ab sofort auf unseren Prozess.

Fuer den reinen Lese-Pfad (Fallback-Backfill via Graph) braucht man
zusaetzlich App-Permission `ChannelMessage.Read.All` oder `Chat.Read.All`
und Admin-Consent. Der Bot-Pfad alleine reicht fuer den normalen Betrieb.

## Architektur

```
src/montblanc/
├─ parsers.py           # .md + .yaml -> Domaenenmodelle
├─ models.py            # pydantic: Los, Mitarbeiter, Tagesplan, Tagesmeldung, ...
├─ planer.py            # Prioritaets-/Deadline-basierte Zuweisung
├─ excel_export.py      # Workbook Uebersicht/Pro-Mitarbeiter/Hinweise
├─ claude_understand.py # messages.parse -> strukturierte Tagesmeldung (Fallback)
├─ teams.py             # Graph-API-Leser (Backfill-Fallback)
├─ config.py            # .env laden
├─ orchestrator.py      # End-to-End
├─ cli.py               # click-CLI (tagesablauf/nur-plan/bot serve/...)
└─ bot/
   ├─ app.py            # aiohttp /api/messages + Adapter-Setup
   ├─ handler.py        # TeamsActivityHandler (Karten-Submit + Freitext)
   ├─ cards.py          # Adaptive-Card-Templates
   ├─ store.py          # TagesmeldungStore (JSON, Bot <-> Orchestrator)
   ├─ refs.py           # ConversationReference-Store fuer proaktives Senden
   └─ proactive.py      # continue_conversation-Helper
```

### Claude-Nutzung (Fallback)

Wenn ein Mitarbeiter *nicht* die Karte ausfuellt, sondern frei schreibt
("Anna, 100 Stueck L-24001 poliert"), dann laeuft `claude_understand.py`:

- Modell: `claude-opus-4-7`
- `messages.parse()` mit pydantic-Schema -> typisiertes Ergebnis
- Kontextblock (bekannte Mitarbeiter, Schritte, Lose) wird gecached
  (`cache_control: ephemeral`) -> jede weitere Meldung am Tag zahlt nur den
  Meldungstext

War alles klar, wird die Meldung direkt im Store gespeichert. War etwas
unklar, setzt Claude `verstanden=false` + `rueckfrage`, und der Bot antwortet
mit einer **Rueckfrage-Karte** (gleiche Felder wie die Tagesmeldungs-Karte,
aber vorbelegt mit dem, was Claude rauslesen konnte).

### Tagesplan-Algorithmus

`planer.erstelle_tagesplan`:

1. Lose nach Prioritaet (hoch > mittel > niedrig) und Deadline sortieren.
2. Pro Los den naechsten Schritt + Mindest-Qualifikation ermitteln.
3. Qualifizierte Mitarbeiter absteigend nach Qualifikationslevel + Restzeit
   sortieren und nacheinander einplanen, bis die Losmenge zugeteilt ist.
4. Dauer/Stueck aus Stammdaten; Endzeit = Start + Menge x Dauer.
5. Hinweise: Lose ohne qualifizierte MA oder ohne Restkapazitaet, sowie
   komplett freie Mitarbeiter.

## Tests

```bash
python -m pytest
```

## Entwicklungsstand

Funktionierend (getestet): Parser, Planer, Excel-Export, Claude-Verstehen,
Adaptive-Cards, TagesmeldungStore.

Offen fuer den Produktivumzug: Bot-Credentials in `.env`, Messaging-Endpoint
in Azure auf die Prozess-URL umbiegen, echte Losstaende/Qualimatrix in
`data/` hinterlegen.
