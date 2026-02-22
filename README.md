v1.0.0 — Post-split stable baseline
# sukkah_teich_sample v1.03.2

Local Teich sample app (PySide6) seeded with Sukkah 2a–4a sample data.

## What’s included
- `data/pdfs/` — Sukkah 2a–4a PDFs (source pages)
- `data/ods/` — ODS with word → English translations (Gemara/Rashi/Tos)
- `data/store/` — Local JSON store created on first run (words/projects/files)

## Run
1) Create / activate a venv
2) Install deps:
   - `pip install pyside6 pandas odfpy numpy pillow pymupdf`
3) Run:
   - `python run_app.py`

## App flow
Home → Create → (Dialogue chooser) → Create page  
Home → Browse → recent/all files + search (files/words)  
Import/Settings are placeholders for now.

## True Daf layout engine (Option A)
The Create page now uses **real, pixel-accurate** segmentation of the central Gemara column into:
- layout **lines**
- approximate **word boxes** per line

This is **segmentation only** (no Hebrew OCR yet). It is enough to drive **Line/Word navigation** exactly by the Vilna layout.

If you don’t install `pymupdf`, the app will still run, but Create will show an instruction banner and won’t generate line layouts.
