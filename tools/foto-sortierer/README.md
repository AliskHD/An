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
5. **OCR** (Tesseract.js, Ziffern-only) versucht die Startnummer aus den
   Info-Bildern zu lesen und fuellt das Feld aus.
6. Du korrigierst manuell, wo die OCR daneben liegt.
   Sobald du eine Nummer eintippst, wird sie auf alle nachfolgenden
   Bilder innerhalb des Zeitfensters propagiert (nur leere Felder werden
   gefuellt – nichts wird ueberschrieben).
7. **Sortieren & Speichern** schreibt umbenannte Kopien nach
   `<dein-Ordner>/sortiert/<Startnummer>/`.

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

- Lass beim Importieren die Schaerfe-Schwelle auf 50; pruefe danach im Grid
  ein paar als "unscharf" markierte – wenn da scharfe Bilder dabei sind,
  Schwelle absenken (z.B. 30) und neu laden.
- **Info-Pattern**: hast du fuer ein Motorrad nur Heckbilder (Startnummer
  nicht sichtbar), dann ist das *vorherige Front-Bild* dein Info-Bild –
  der Auto-Cluster setzt das Flag automatisch, OCR liest die Nummer von
  vorne, und die Heckbilder erben sie ueber die Vorwaerts-Propagation.
- **OCR-Genauigkeit**: motorraennummern sind nicht perfekt fuer Tesseract
  (Schraege, Schmutz, Sticker). OCR ist eine Vorschlag-Hilfe, kein Auto-Pilot.
- Bei der Startnummer reichen 1-4 Ziffern – wird beim Speichern auf 4 Stellen
  gepaddet.

## Bekannte Grenzen

- Keine RAW-Vorschau (CR3, ARW, NEF). Die Datei laesst sich noch lesen und
  umbenennen, aber das Thumbnail bleibt leer. Wenn du JPEG+RAW schiesst,
  importier die JPEGs hier.
- File System Access verlangt einen User-Klick zum Oeffnen – kein Drag&amp;Drop
  ganzer Ordner moeglich.
- Tesseract laedt beim ersten OCR-Klick ein paar MB an WASM nach (Internet-
  Verbindung noetig). Danach laeuft alles offline weiter.
