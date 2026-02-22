from __future__ import annotations
from pathlib import Path
from typing import Dict, Any
import pandas as pd

from .store import DataStore

def import_ods_words(ds: DataStore, ods_path: Path) -> Dict[str, Any]:
    """
    Import all sheets from the provided ODS into words store.
    We treat each row as: word_raw, word_nikud, english, source (4 cols).
    """
    ods_path = Path(ods_path)
    sheets = pd.read_excel(str(ods_path), sheet_name=None, engine="odf", header=None)

    added = 0
    for sheet_name, df in sheets.items():
        # ensure at least 4 columns
        if df.shape[1] < 4:
            continue
        df = df.iloc[:, :4]
        df.columns = ["word_raw", "word_nikud", "english", "source"]

        for _, row in df.iterrows():
            word_raw = "" if pd.isna(row["word_raw"]) else str(row["word_raw"]).strip()
            word_nikud = "" if pd.isna(row["word_nikud"]) else str(row["word_nikud"]).strip()
            english = "" if pd.isna(row["english"]) else str(row["english"]).strip()
            source = "" if pd.isna(row["source"]) else str(row["source"]).strip()

            if not (word_raw or english):
                continue
            ds.upsert_word(word_raw, word_nikud, english, source, sheet=sheet_name)
            added += 1

    # Register the import as a single "file"
    ds.register_import(import_id=f"import_{ods_path.stem}", title=f"Imported ODS: {ods_path.name}")
    ds.save_all()

    return {"rows_seen": int(sum(len(df) for df in sheets.values())), "added": added, "sheets": list(sheets.keys())}
