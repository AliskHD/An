# Mont Blanc Tagesplanung

Automatisiert den taeglichen Ablauf in der Mont Blanc Abteilung:

1. **Liest** die Tagesmeldungen der Mitarbeiter aus dem Microsoft Teams Chat.
2. **Versteht** die Meldungen mit der Claude API – bei Unklarheit wird eine
   Rueckfrage in Teams gepostet.
3. **Schreibt** die Losstaende fort.
4. **Erstellt** den Tagesplan fuer morgen aus Losstaenden, Qualifikationsmatrix
   und Prozessstammdaten.
5. **Exportiert** den Plan als Excel und **postet** ihn im Teams-Chat.

## Daten

Alle Stammdaten liegen als Markdown / YAML unter `data/`:

| Datei                         | Inhalt                                          |
|-------------------------------|-------------------------------------------------|
| `losstaende.md`               | Aktive Lose mit Menge, Schritt, Prioritaet      |
| `qualifikationsmatrix.md`     | Mitarbeiter x Prozessschritt, Qualifikationslevel 0-3 |
| `stammdaten.yaml`             | Prozessschritte (Dauer/Stueck, Mindest-Quali), Schicht |

Datenpflege passiert direkt in diesen Dateien; der Code liest sie bei jedem Lauf
neu ein.

## Installation

```bash
pip install -e .
cp .env.example .env      # dann Secrets eintragen
```

## Benutzung

**Nur Tagesplan erzeugen** (ohne Teams/Claude, aus den .md-Dateien):

```bash
montblanc nur-plan --datum 2026-04-22
```

**Kompletter Tagesablauf** (Teams lesen -> Claude verstehen -> Plan -> Teams-Post):

```bash
montblanc tagesablauf --tag 2026-04-21
```

`--tag` ist der Tag der Meldungen (Default: heute). Geplant wird fuer den
Folgetag.

## Architektur

```
src/montblanc/
├─ parsers.py          # .md + .yaml -> Domaenenmodelle
├─ models.py           # pydantic: Los, Mitarbeiter, Tagesplan, Tagesmeldung, ...
├─ planer.py           # erstelle_tagesplan: prioritaetsbasierte Zuweisung
├─ excel_export.py     # Workbook mit Tagesplan/Pro-Mitarbeiter/Hinweise-Sheet
├─ teams.py            # Graph-API (lesen) + Power Automate Webhook (schreiben)
├─ claude_understand.py# Claude messages.parse -> strukturierte Tagesmeldung
├─ config.py           # .env laden
├─ orchestrator.py     # End-to-End-Ablauf
└─ cli.py              # click-CLI
```

### Teams-Integration

**Lesen** erfolgt ueber Microsoft Graph mit App-Auth (Client Credentials).
Benoetigte App-Permissions (Admin-Consent):

- `ChannelMessage.Read.All` – falls die Reports in einem Team-Channel landen
- `Chat.Read.All`           – falls sie in einem Gruppen-Chat landen

**Schreiben** laeuft bewusst nicht direkt ueber Graph, weil App-Permissions
fuer Chat-Nachrichten als *Protected APIs* zu beantragen sind. Stattdessen
gibt es einen Power Automate Flow "HTTP Request empfangen":

1. HTTP-Trigger mit JSON `{nachricht, dateiname, datei_base64}`
2. Base64 dekodieren, Datei in SharePoint/OneDrive ablegen
3. Teams-Nachricht im Ziel-Chat posten (mit Link/Kachel)

Der Flow-URL landet als Secret in `.env` (`POWER_AUTOMATE_WEBHOOK_URL`).

### Claude-Einsatz

In `claude_understand.py`:

- Modell: `claude-opus-4-7`
- `messages.parse()` mit pydantic-Schema -> typisierte Antwort ohne JSON-Gefrickel
- Kontextblock (bekannte Mitarbeiter, Schritte, Lose) wird **gecached**
  (`cache_control: ephemeral`), nur der Meldungstext pro Anfrage kostet voll
- Bei fehlender/unklarer Info setzt Claude `verstanden=False` und formuliert
  die Rueckfrage – der Orchestrator postet sie ueber den Power Automate Flow

### Tagesplan-Algorithmus

`planer.erstelle_tagesplan`:

1. Lose nach Prioritaet (hoch > mittel > niedrig) und Deadline sortieren.
2. Pro Los den naechsten Schritt + Mindest-Qualifikation ermitteln.
3. Qualifizierte Mitarbeiter absteigend nach Qualifikationslevel + Restzeit
   sortieren und nacheinander einplanen, bis die Losmenge zugeteilt ist.
4. Dauer pro Stueck aus den Stammdaten; Endzeit = Start + Menge x Dauer.
5. Hinweise: Lose ohne qualifizierte MA oder ohne Restkapazitaet, sowie
   komplett freie MA.

## Tests

```bash
python -m pytest
```

## Entwicklungsstand

Funktionierend: Parser, Planer, Excel-Export, Claude-Verstehen, Teams-Reader.
Offen fuer den Produktivumzug: echte Teams-Credentials in `.env`, Power
Automate Flow anlegen und URL eintragen, echte Losstaende/Qualimatrix in
`data/` hinterlegen.
