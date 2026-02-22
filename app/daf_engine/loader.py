from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Tuple

from .model import PageLayout, LineLayout, WordBox


def _layout_key(masechta: str, daf: int, amud: str) -> str:
    return f"{masechta.lower()}_{daf}{amud.lower()}"


def load_layout(json_path: Path) -> PageLayout:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    lines: list[LineLayout] = []

    for ln in data.get("lines", []):
        words = [WordBox(**w) for w in ln.get("words", [])]
        lines.append(
            LineLayout(
                line_no=int(ln.get("line_no", 0) or 0),
                y0=int(ln.get("y0", 0) or 0),
                y1=int(ln.get("y1", 0) or 0),
                words=words,
            )
        )

    col = tuple(int(x) for x in data.get("column_bbox", [0, 0, 0, 0]))
    meta = dict(data.get("meta", {}))

    return PageLayout(
        masechta=str(data.get("masechta", "Sukkah")),
        daf=int(data.get("daf", 2)),
        amud=str(data.get("amud", "a")),
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
    except Exception as e:
        return None, f"Failed to load layout JSON ({json_path.name}): {e}"
