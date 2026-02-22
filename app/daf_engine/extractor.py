from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Optional

import numpy as np

from .model import PageLayout, LineLayout, WordBox


def _have_pymupdf() -> bool:
    try:
        import fitz  # type: ignore
        _ = fitz
        return True
    except Exception:
        return False


def _render_pdf_first_page(pdf_path: Path, out_png: Path, zoom: float = 2.0) -> None:
    """Render PDF page 1 to PNG using PyMuPDF (fitz)."""
    import fitz  # type: ignore

    doc = fitz.open(str(pdf_path))
    page = doc.load_page(0)
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    pix.save(str(out_png))



def _extract_textlayer_words(pdf_path: Path, zoom: float) -> list[tuple[float,float,float,float,str]]:
    """Return list of (x0,y0,x1,y1,text) in *pixel* coords at given zoom.
    If no text layer, returns empty list.
    """
    try:
        import fitz  # type: ignore
    except Exception:
        return []
    try:
        doc = fitz.open(str(pdf_path))
        page = doc.load_page(0)
        words = page.get_text("words")  # x0,y0,x1,y1,word,block,line,word_no
    except Exception:
        return []
    out = []
    for w in words:
        if len(w) < 5:
            continue
        x0,y0,x1,y1,text = w[0],w[1],w[2],w[3],w[4]
        if not isinstance(text, str):
            continue
        t = text.strip()
        if not t:
            continue
        out.append((float(x0*zoom), float(y0*zoom), float(x1*zoom), float(y1*zoom), t))
    return out


def _group_words_to_text_lines(words: list[tuple[float,float,float,float,str]], y_tol: float = 3.0) -> list[dict]:
    """Group word boxes into text lines by y center proximity.
    Returns list of dicts: {y: float, words: [(x0,x1,text), ...]} sorted top->bottom.
    """
    items = []
    for x0,y0,x1,y1,t in words:
        yc = (y0 + y1) / 2.0
        items.append((yc, x0, x1, t, y0, y1))
    items.sort(key=lambda r: r[0])

    lines: list[dict] = []
    for yc, x0, x1, t, y0, y1 in items:
        if not lines or abs(lines[-1]["y"] - yc) > y_tol:
            lines.append({"y": yc, "words": [(x0, x1, t)], "y0": y0, "y1": y1})
        else:
            lines[-1]["words"].append((x0, x1, t))
            lines[-1]["y0"] = min(lines[-1]["y0"], y0)
            lines[-1]["y1"] = max(lines[-1]["y1"], y1)

    # Sort words within each line. For Hebrew RTL, we want right->left, so sort by x0 descending.
    for ln in lines:
        ln["words"].sort(key=lambda w: w[0], reverse=True)

    return lines


def _otsu_threshold(gray: np.ndarray) -> int:
    """Compute Otsu threshold for 8-bit grayscale image."""
    hist = np.bincount(gray.reshape(-1), minlength=256).astype(np.float64)
    total = gray.size
    sum_total = np.dot(np.arange(256), hist)
    sum_b = 0.0
    w_b = 0.0
    max_var = -1.0
    threshold = 127
    for t in range(256):
        w_b += hist[t]
        if w_b == 0:
            continue
        w_f = total - w_b
        if w_f == 0:
            break
        sum_b += t * hist[t]
        m_b = sum_b / w_b
        m_f = (sum_total - sum_b) / w_f
        var_between = w_b * w_f * (m_b - m_f) ** 2
        if var_between > max_var:
            max_var = var_between
            threshold = t
    return int(threshold)


def _load_image_as_gray(png_path: Path) -> np.ndarray:
    from PIL import Image

    im = Image.open(png_path).convert("L")
    return np.array(im)


def _find_main_text_vertical_extent(ink: np.ndarray) -> tuple[int, int]:
    """Find y-range where the main page has text (ignore top/bottom whitespace)."""
    h, w = ink.shape
    row_ink = ink.mean(axis=1)
    # heuristic thresholds tuned for Vilna prints: ink density is usually low but non-zero
    thr = max(0.01, float(np.percentile(row_ink, 65)))
    ys = np.where(row_ink > thr)[0]
    if ys.size == 0:
        return 0, h - 1
    y0 = int(max(0, ys[0] - 10))
    y1 = int(min(h - 1, ys[-1] + 10))
    return y0, y1


def _find_gemara_column_bbox(ink: np.ndarray, safe_center=(0.18, 0.82)) -> tuple[int, int, int, int]:
    """Locate dominant central column by vertical ink projection."""
    h, w = ink.shape
    y0, y1 = _find_main_text_vertical_extent(ink)
    band = ink[y0 : y1 + 1, :]

    col = band.mean(axis=0)
    # smooth by a simple box filter
    k = 61
    pad = k // 2
    col_p = np.pad(col, (pad, pad), mode="edge")
    col_s = np.convolve(col_p, np.ones(k) / k, mode="valid")

    left_lim = int(safe_center[0] * w)
    right_lim = int(safe_center[1] * w)
    col_mid = col_s[left_lim:right_lim]

    # threshold: above a fraction of the max
    thr = max(0.015, float(col_mid.max() * 0.35))
    in_text = col_mid > thr
    if not np.any(in_text):
        return int(0.25 * w), y0, int(0.75 * w), y1

    # longest contiguous run
    idx = np.where(in_text)[0]
    runs = []
    start = idx[0]
    prev = idx[0]
    for i in idx[1:]:
        if i == prev + 1:
            prev = i
        else:
            runs.append((start, prev))
            start = prev = i
    runs.append((start, prev))

    best = max(runs, key=lambda r: (r[1] - r[0]))
    x0 = left_lim + int(best[0])
    x1 = left_lim + int(best[1])
    # add padding
    x0 = max(0, x0 - 6)
    x1 = min(w - 1, x1 + 6)
    return x0, y0, x1, y1


def _detect_line_bands(ink_col: np.ndarray) -> list[tuple[int, int]]:
    """Detect horizontal line bands inside the cropped gemara column."""
    h, w = ink_col.shape
    row = ink_col.mean(axis=1)
    # dynamic threshold: line rows have more ink than empty rows
    thr = max(0.01, float(np.percentile(row, 70)) * 0.9)
    mask = row > thr

    bands: list[tuple[int, int]] = []
    y = 0
    while y < h:
        if not mask[y]:
            y += 1
            continue
        y0 = y
        while y < h and mask[y]:
            y += 1
        y1 = y - 1
        # filter tiny bands
        if (y1 - y0 + 1) >= 6:
            bands.append((y0, y1))

    # merge bands separated by tiny gaps (helps with nikud / thin strokes)
    merged: list[tuple[int, int]] = []
    for b in bands:
        if not merged:
            merged.append(b)
            continue
        p0, p1 = merged[-1]
        if b[0] - p1 <= 4:
            merged[-1] = (p0, b[1])
        else:
            merged.append(b)
    return merged


def _split_words_by_projection(ink_line: np.ndarray) -> list[tuple[int, int]]:
    """Split a line into word boxes by vertical projection gaps."""
    h, w = ink_line.shape
    col = ink_line.mean(axis=0)
    thr = max(0.01, float(np.percentile(col, 65)) * 0.8)
    mask = col > thr

    # Require a minimum gap width to split words
    gap_min = max(6, int(0.012 * w))

    # Find contiguous ink runs, but merge small gaps
    x = 0
    boxes: list[tuple[int, int]] = []
    while x < w:
        if not mask[x]:
            x += 1
            continue
        x0 = x
        while x < w and mask[x]:
            x += 1
        x1 = x - 1

        # extend a bit
        x0 = max(0, x0 - 1)
        x1 = min(w - 1, x1 + 1)
        boxes.append((x0, x1))

    if not boxes:
        return []

    # merge boxes that are too close
    merged = [boxes[0]]
    for b in boxes[1:]:
        p0, p1 = merged[-1]
        if b[0] - p1 < gap_min:
            merged[-1] = (p0, b[1])
        else:
            merged.append(b)

    # Filter very thin "words"
    out = [(a, b) for (a, b) in merged if (b - a + 1) >= 10]
    return out


def extract_pdf_to_layout(pdf_path: Path, out_json: Path, out_png: Path, *, masechta: str, daf: int, amud: str) -> PageLayout:
    """Create a layout JSON with real (pixel-accurate) line segmentation.

    Notes:
    - This does NOT OCR the Hebrew text. It produces real line/word bounding boxes.
    - Later, we can plug in OCR for actual word strings.
    """
    if not _have_pymupdf():
        raise RuntimeError("Missing dependency: PyMuPDF (pymupdf). Install with: pip install pymupdf")

    _render_pdf_first_page(pdf_path, out_png, zoom=2.0)
    gray = _load_image_as_gray(out_png)

    t = _otsu_threshold(gray)
    # ink = 1.0 for black, 0.0 for white
    ink = (gray < t).astype(np.float32)

    x0, y0, x1, y1 = _find_gemara_column_bbox(ink)
    col = ink[y0 : y1 + 1, x0 : x1 + 1]

    bands = _detect_line_bands(col)

    lines: list[LineLayout] = []
    for i, (ly0, ly1) in enumerate(bands, start=1):
        line_ink = col[ly0 : ly1 + 1, :]
        word_boxes = _split_words_by_projection(line_ink)
        words = [WordBox(word_no=j + 1, x0=int(wx0), x1=int(wx1)) for j, (wx0, wx1) in enumerate(word_boxes)]
        lines.append(LineLayout(line_no=i, y0=int(y0 + ly0), y1=int(y0 + ly1), words=words))
    # Try to attach *actual word text* from PDF text-layer (if available).
    # This is critical for word-based selection UX. If the PDF has no text-layer,
    # WordBox.text will remain empty and the UI can prompt for OCR later.
    text_words = _extract_textlayer_words(pdf_path, zoom=2.0) if _have_pymupdf() else []
    # Filter to the detected Gemara column bbox (with small margins)
    if text_words:
        mx0, my0, mx1, my1 = x0 - 8, y0 - 8, x1 + 8, y1 + 8
        text_words = [w for w in text_words if (mx0 <= w[0] <= mx1 and mx0 <= w[2] <= mx1 and my0 <= w[1] <= my1 and my0 <= w[3] <= my1)]
    text_lines = _group_words_to_text_lines(text_words, y_tol=4.0) if text_words else []
    assigned = 0
    if text_lines:
        # Map each text line to the closest detected line by y center.
        line_centers = [((ln.y0 + ln.y1) / 2.0) for ln in lines]
        for tl in text_lines:
            yc = tl["y"]
            # find closest detected line
            best_i = min(range(len(line_centers)), key=lambda i: abs(line_centers[i] - yc))
            target = lines[best_i]
            texts = [t for (_x0, _x1, t) in tl["words"]]
            for j in range(min(len(target.words), len(texts))):
                target.words[j].text = texts[j]
                assigned += 1

    # store light diagnostics
    meta = {
        "zoom": 2.0,
        "textlayer_words": len(text_words),
        "textlayer_lines": len(text_lines),
        "text_assigned": assigned,
        "has_textlayer": bool(text_words),
    }


    layout = PageLayout(
        masechta=masechta,
        daf=daf,
        amud=amud,
        page_image=str(out_png.name),
        column_bbox=(int(x0), int(y0), int(x1), int(y1)),
        lines=lines,
        meta={
            **meta,
            "pdf": pdf_path.name,
            "render_zoom": 2.0,
            "threshold": int(t),
            "note": "Segmentation + PDF text-layer (when available).",
        },
    )

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_png.parent.mkdir(parents=True, exist_ok=True)

    payload = asdict(layout)
    payload["column_bbox"] = list(layout.column_bbox)
    with out_json.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    return layout


def load_layout(json_path: Path) -> PageLayout:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    lines: list[LineLayout] = []
    for ln in data.get("lines", []):
        words = [WordBox(**w) for w in ln.get("words", [])]
        lines.append(LineLayout(line_no=int(ln["line_no"]), y0=int(ln["y0"]), y1=int(ln["y1"]), words=words))
    col = tuple(int(x) for x in data.get("column_bbox", [0, 0, 0, 0]))
    return PageLayout(
        masechta=data.get("masechta", "Sukkah"),
        daf=int(data.get("daf", 2)),
        amud=str(data.get("amud", "a")),
        page_image=str(data.get("page_image", "")),
        column_bbox=col,  # type: ignore
        lines=lines,
        meta=dict(data.get("meta", {})),
    )


def ensure_page_layout(
    project_root: Path,
    *,
    masechta: str,
    daf: int,
    amud: str,
    pdf_path: Path,
) -> tuple[Optional[PageLayout], Optional[str]]:
    """Ensure JSON + rendered PNG exist. Returns (layout, error_message)."""
    data_root = project_root / "data"
    layouts_dir = data_root / "layouts"
    pages_dir = data_root / "pages"

    key = f"{masechta.lower()}_{daf}{amud}"
    out_json = layouts_dir / f"{key}.json"
    out_png = pages_dir / f"{key}.png"

    if out_json.exists() and out_png.exists():
        try:
            return load_layout(out_json), None
        except Exception as e:
            return None, f"Failed to load existing layout: {e}"

    try:
        layout = extract_pdf_to_layout(
            pdf_path,
            out_json,
            out_png,
            masechta=masechta,
            daf=daf,
            amud=amud,
        )
        return layout, None
    except Exception as e:
        return None, str(e)
