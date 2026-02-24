# Teich — Sukkah Sample (v1.05.2)

Local Teich sample desktop app (PySide6) seeded with Sukkah 2a–4b demo layout JSON + an ODS word list.

## What’s included
- `data/layouts/` — demo layout JSON for Sukkah 2a–4b (GUI demo mode: 6 words per line)
- `data/ods/` — ODS with word → English translations
- `data/store/` — local JSON store (words/projects/files)

## Run
1) Create / activate a venv
2) Install deps:
   - `pip install -r requirements.txt`
3) Run:
   - `python run_app.py`

## App flow
- **Home → Create**
  - **Create Picker page**: choose daf + start/end word, then **Generate**
  - **Create Editor page**: full-screen table + **Save** + **Back to Picker**
  - **Explanation matching**: double-click the **Explanation** cell to pick from stored word entries
  - **Unsaved changes**: Back / window close prompts Save / Don’t Save / Cancel
- **Home → Browse**
  - Working Pages list supports **right-click → Delete**

## Architecture rule (locked)
This repo is GUI-only. Layout JSON is the boundary contract from Teich-WordMapper.
