# Motorrad Foto Sortierer

Browser-Tool zum Sortieren und Umbenennen von Rennstrecken-Fotos nach Startnummer.

## Was es macht

1. Du oeffnest den Ordner mit den Fotos.
2. Tool sortiert chronologisch nach EXIF-Aufnahmezeit.
3. **Schaerfe-Score** (Laplacian-Varianz) laeuft automatisch im Hintergrund;
   unscharfe Bilder werden direkt als verworfen markiert (Schwelle einstellbar).
4. **Auto-Cluster** gruppiert alles, was innerhalb des Zeitfensters
   (Default 60 s) hintereinander aufgenommen wurde – das erste Bild jeder Gruppe
   wird als **Info-Bild** markiert.
5. **OCR** (Tesseract.js, Ziffern-Whitelist) auf einer **selbst gezogenen
   Region**: Klick aufs Foto → Lightbox, Maus-Rechteck um die Startnummer
   ziehen, „OCR diese Region" klicken. Die Region wird gemerkt (localStorage)
   und „Auf alle Info-Bilder anwenden" laeuft sie auf der ganzen Session ab.
6. Du korrigierst manuell, wo die OCR daneben liegt.
   Sobald du eine Nummer eintippst, wird sie auf alle nachfolgenden
   Bilder innerhalb des Zeitfensters propagiert (nur leere Felder werden
   gefuellt – nichts wird ueberschrieben).
7. **Sortieren & Speichern** schreibt umbenannte Kopien nach
   `<dein-Ordner>/sortiert/<Startnummer>/`.

## OCR-Engines: Claude oder Tesseract

Tesseract.js (offline, gratis) erkennt stilisierte Race-Schriften
**unzuverlaessig** – im Schnitt 30-60 % Treffer, je nach Bild. Fuer
ernsthaftes Sortieren reicht das nicht.

**Empfohlen: Claude Vision.** Kopiere deinen Anthropic-API-Key in das
Feld „Anthropic API Key" im Header. Der Schluessel landet im
localStorage des Browsers (nicht in der Cloud, nicht im Repo). Sobald
gesetzt, schaltet die OCR auf Claude (`claude-haiku-4-5`) um:

- ~99 % Trefferquote bei sauber gezogenem ROI
- ~0,3 ct pro Bild → 1000 Fotos kosten ca. 3 €
- Bis zu 5 Bilder parallel beim Batch-Run

Ohne API-Key wird automatisch auf Tesseract zurueckgefallen (mit allen
oben genannten Vorbehalten).

## Warum Region-OCR statt Voll-OCR?

Voll-Bild-OCR auf Rennsport-Fotos liefert Schrott: Sponsoren-Stickers,
Lap-Timer-Anzeigen, Zahlen auf Helmen und Reifen werden alle mit aufgesammelt.
Mit einer engen Region um die Frontnummer (Scheibe oder Schutzblech) faellt
das alles weg, dazu wird die Region:

- 3-fach hochskaliert (mindestens 600 px lange Kante)
- in mehreren Varianten geprueft (Graustufen, Otsu-Threshold, invertiert)
- mit `tessedit_pageseg_mode=7` (single text line) ausgewertet

Die Variante mit der hoechsten Tesseract-Konfidenz gewinnt; bei
Konfidenz unter `OCR Min-Konfidenz` (Default 55) wird nichts gefuellt.

Wenn du in der Session die Bildkomposition aenderst (Standortwechsel,
neuer Bildausschnitt), zieh einfach im naechsten Lightbox-Bild eine neue
Region – die alte wird ueberschrieben.

## Dateinamen-Schema

```
0026_260506_Most_001_0026.jpg
└─┬─┘ └──┬─┘ └─┬┘ └┬┘ └─┬─┘
  │     │      │   │     └─ Startnummer (4-stellig, gepaddet)
  │     │      │   └─────── Fortlaufende Nummer dieser Startnummer (3-stellig)
  │     │      └─────────── Rennstrecke (Eingabefeld)
  │     └────────────────── Datum YYMMDD (Eingabefeld)
  └──────────────────────── Startnummer (4-stellig, gepaddet)
```

Die Originale bleiben unangetastet; es werden Kopien geschrieben.

## Anforderungen

- **Chrome, Edge oder Opera** (File System Access API – Firefox/Safari koennen
  noch keine Ordner-Schreibrechte gewaehren).
- Datei einfach lokal oeffnen: `tools/foto-sortierer/index.html` doppelklicken,
  oder serven mit `python -m http.server` aus dem Repo-Root und
  `http://localhost:8000/tools/foto-sortierer/` aufrufen.

## Workflow-Tipps

- **Reihenfolge:**
  1. Ordner laden, kurz warten bis Schaerfe gemessen ist.
  2. „Auto-Cluster" → Info-Flags werden gesetzt.
  3. Auf ein gut sichtbares Foto klicken (Front, Nummer auf Scheibe).
  4. Im Lightbox Maus-Rechteck eng um die Nummer ziehen.
  5. „OCR diese Region" → Konfidenz pruefen.
     - Trifft → „Auf alle Info-Bilder anwenden".
     - Trifft nicht → Region groesser/kleiner ziehen, anderes Foto, anderer Ausschnitt.
  6. Manuell korrigieren, wo OCR unsicher ist (Badge „OCR 38%" -> haendisch nachpflegen).
  7. „Sortieren &amp; Speichern".
- **Info-Pattern**: hast du fuer ein Motorrad nur Heckbilder (Startnummer
  nicht sichtbar), dann ist das *vorherige Front-Bild* dein Info-Bild –
  der Auto-Cluster setzt das Flag automatisch, OCR liest die Nummer von
  vorne, und die Heckbilder erben sie ueber die Vorwaerts-Propagation.
- **2- und 3-stellige Startnummern** (typisch 48, 99, 990) werden im Filename
  auf 4 Stellen gepaddet (`0048_…`, `0990_…`), damit die Sortierung sauber
  bleibt – im Eingabefeld tippst du nur die Ziffern, ohne fuehrende Nullen.
- **OCR-Genauigkeit**: Race-Nummern sind keine genormten Schilder. Schraege,
  Schmutz, Sticker und tiefe Schatten kosten Konfidenz. Mit einer engen ROI
  + Otsu-Threshold liegen wir typisch in 70-90 % Bereich; alles unter der
  Min-Konfidenz wird liegen gelassen statt falsch gefuellt.

## Bekannte Grenzen

- Keine RAW-Vorschau (CR3, ARW, NEF). Die Datei laesst sich noch lesen und
  umbenennen, aber das Thumbnail bleibt leer. Wenn du JPEG+RAW schiesst,
  importier die JPEGs hier.
- File System Access verlangt einen User-Klick zum Oeffnen – kein Drag&amp;Drop
  ganzer Ordner moeglich.
- Tesseract laedt beim ersten OCR-Klick ein paar MB an WASM nach (Internet-
  Verbindung noetig). Danach laeuft alles offline weiter.
