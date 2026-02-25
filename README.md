# Teich — Sukkah Sample (v1.05.3)

A desktop application for learning and annotating Talmudic texts, built with PySide6. This sample includes Sukkah 2a–4b with demo layouts and an ODS-based word dictionary.

## Overview

**Teich** is a tool for creating, browsing, and exporting annotated Talmudic study materials. It lets you:
- Browse imported word dictionaries (Hebrew/Nikud/English)
- Create working pages tied to specific Talmudic passages
- Add explanations and link them to word entries
- Save and export your work
- Manage multiple projects

## Tech Stack
- **PySide6** — Qt desktop GUI framework
- **Python 3.12** — Core language
- **JSON** — Local data storage (words, projects, files)
- **ODS** — Word list import format (LibreOffice Calc)
- **PDF/DOCX** — Export formats

## Project Structure

```
├── run_app.py                    # Entry point
├── requirements.txt              # Python dependencies
├── README.md                     # This file
├── app/
│   ├── app.py                   # Main application window & routing
│   ├── store.py                 # DataStore class (JSON persistence)
│   ├── import_ods.py            # ODS word list import utility
│   ├── widgets.py               # Reusable UI components (Card, TopBar)
│   ├── theme.py                 # Application styling (stylesheet)
│   ├── utils_hebrew.py          # Hebrew text utilities (normalization)
│   ├── match_picker_dialog.py   # Dialog for matching/linking words
│   │
│   ├── daf_engine/              # Layout loading & daf management
│   │   ├── loader.py            # JSON layout loader
│   │   ├── model.py             # Daf data model
│   │   └── __init__.py
│   │
│   ├── models/                  # Data models
│   │   ├── selection.py         # Word selection model
│   │   └── __init__.py
│   │
│   └── pages/                   # Application pages (stack layout)
│       ├── home.py              # Home page with navigation
│       ├── browse.py            # Browse projects/files & word dictionary
│       ├── create_picker.py     # Pick daf & word range to create project
│       ├── create_editor.py     # Full-screen editor for annotation
│       ├── create_shared.py     # Shared utilities for create pages
│       ├── export_page.py       # Export projects to PDF/DOCX
│       └── __init__.py
│
└── data/
    ├── layouts/                 # Demo layout JSON files (Sukkah 2a–4b)
    │   ├── sukkah_2a.json
    │   ├── sukkah_2b.json
    │   ├── sukkah_3a.json
    │   ├── sukkah_3b.json
    │   ├── sukkah_4a.json
    │   └── sukkah_4b.json
    ├── ods/                     # ODS word list files (import source)
    │   └── [sample.ods]         # Place ODS files here for import
    └── store/                   # Local data store (created at runtime)
        ├── words.json           # Imported & manually added words
        ├── projects.json        # Working pages / projects
        ├── files.json           # File registry (imports/exports)
        └── templates.json       # (For future use)
```

## Quick Start

### 1. Setup Environment
```bash
# Create virtual environment
python -m venv .venv

# Activate it
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Run the App
```bash
python run_app.py
```

The app window opens with the Home page. A demo ODS file (if present in `data/ods/`) is automatically imported.

## User Guide

### Home Page
Navigation hub. Choose:
- **Create** -> Start a new working page
- **Browse** -> View & manage projects, browse word dictionary
- **Export** -> Export completed projects (PDF/DOCX)
- **Import** – Coming soon
- **Settings** – Coming soon

### Create Flow
1. **Create Picker Page**
   - Select **Masechta** (Sukkah, etc.)
   - Choose **Perek** (section)
   - Pick **Daf** (page) from available layouts
   - Set **Word Range** (start/end words)
   - Click **Generate** to create the working page

2. **Create Editor Page**
   - Full-screen table shows all words for your selection
   - **Double-click Explanation cell** to pick from imported words (links to dictionary)
   - Edit explanations inline
   - Click **Save** to store project, **Back** to return to picker
   - Unsaved changes trigger a save dialog when navigating away

### Browse Page
- **Files View** (default)
  - **Recent** – Last 10 projects you opened
  - **Imported** – Word lists imported from ODS
  - **Working Pages** – Active/editable projects (right-click to rename/delete)
  - **Saved/Exported** – Completed exports (PDF/DOCX)
  
- **Words View** (toggle via "Words" button)
  - Search imported dictionary by word, Nikud, or English
  - **Right-click** to Add/Edit/Delete words manually
  - Rows show: Word (Hebrew) | Nikud (vowels) | English (translation)

### Export Page
Convert completed project to:
- **PDF** – For printing/sharing
- **DOCX** – For editing in Word

## Data Storage

All user data is stored locally in `data/store/` as JSON:

- **`words.json`** – Dictionary entries (id, word_raw, word_nikud, english, hebrew, sources)
- **`projects.json`** – Working pages (id, title, daf, masechta, rows with explanations, metadata)
- **`files.json`** – Registry of imports & exports (id, title, kind, format, created_at)

No external database needed. Data persists between app sessions.

## Architecture

- **GUI-only design** – Application is 100% UI layer. Layout JSON is the contract boundary with Teich-WordMapper.
- **Modular pages** – Each page is a QWidget in a QStackedLayout. Navigation via signals.
- **Centralized data** – DataStore handles all JSON I/O and caching.
- **Responsive** – Search/filtering updates instantly as you type.

## Troubleshooting

**"No .ods file found" warning:**
- Place an ODS word list in `data/ods/` before starting the app
- ODS must have columns: Word | Nikud | English

**Display warnings (Qt/PySide6):**
- Harmless warnings about monitor enumeration; can be ignored
- Ensure all connected displays are enabled in Windows settings

**Import errors:**
- Verify `requirements.txt` was installed: `pip install -r requirements.txt`
- Use Python 3.12 for best results
