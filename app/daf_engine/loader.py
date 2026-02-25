from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Tuple

from .model import PageLayout, LineLayout, WordBox


def _layout_key(masechta: str, daf: int, amud: str) -> str:
    return f"{masechta.lower()}_{daf}{amud.lower()}"


def load_layout(json_path: Path) -> PageLayout:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    
    # Validate required fields
    if "masechta" not in data:
        raise ValueError(f"Layout JSON missing required field 'masechta' in {json_path.name}")
    if "daf" not in data:
        raise ValueError(f"Layout JSON missing required field 'daf' in {json_path.name}")
    if "amud" not in data:
        raise ValueError(f"Layout JSON missing required field 'amud' in {json_path.name}")
    if "lines" not in data or not isinstance(data["lines"], list):
        raise ValueError(f"Layout JSON missing or invalid 'lines' array in {json_path.name}")
    
    lines: list[LineLayout] = []

    for idx, ln in enumerate(data["lines"]):
        if not isinstance(ln, dict):
            raise ValueError(f"Line {idx} is not a valid object in {json_path.name}")
        if "line_no" not in ln:
            raise ValueError(f"Line {idx} missing 'line_no' in {json_path.name}")
        if "words" not in ln or not isinstance(ln["words"], list):
            raise ValueError(f"Line {idx} missing or invalid 'words' array in {json_path.name}")
        
        words = []
        for w_idx, w in enumerate(ln["words"]):
            if not isinstance(w, dict):
                raise ValueError(f"Line {idx}, word {w_idx} is not a valid object in {json_path.name}")
            if "word_no" not in w or "x0" not in w or "x1" not in w:
                raise ValueError(f"Line {idx}, word {w_idx} missing required fields in {json_path.name}")
            words.append(WordBox(**w))
        
        lines.append(
            LineLayout(
                line_no=int(ln["line_no"]),
                y0=int(ln.get("y0", 0)),
                y1=int(ln.get("y1", 0)),
                words=words,
            )
        )

    col = tuple(int(x) for x in data.get("column_bbox", [0, 0, 0, 0]))
    meta = dict(data.get("meta", {}))

    return PageLayout(
        masechta=str(data["masechta"]),
        daf=int(data["daf"]),
        amud=str(data["amud"]),
        page_image=str(data.get("page_image", "")),
        column_bbox=col,  # type: ignore
        lines=lines,
        meta=meta,
    )


def ensure_page_layout(
    project_root: Path,
    *,
    masechta: str,
    daf: int,
    amud: str,
    pdf_path: Optional[Path] = None,  # kept for backwards-compat; ignored in GUI-only repo
) -> Tuple[Optional[PageLayout], Optional[str]]:
    """GUI-only contract:

    - Never renders PDFs.
    - Never segments images.
    - Only loads the wordmap/layout JSON produced elsewhere.

    Expected file: data/layouts/<masechta>_<daf><amud>.json
    """
    data_root = Path(project_root) / "data"
    layouts_dir = data_root / "layouts"

    key = _layout_key(masechta, daf, amud)
    json_path = layouts_dir / f"{key}.json"

    if not json_path.exists():
        return None, f"Missing layout JSON: {json_path.name}"

    try:
        layout = load_layout(json_path)
        return layout, None
    except (json.JSONDecodeError, ValueError) as e:
        return None, f"Invalid layout JSON ({json_path.name}): {e}"
    except (IOError, OSError) as e:
        return None, f"Cannot read layout JSON ({json_path.name}): {e}"
