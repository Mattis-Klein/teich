from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class WordBox:
    """A word box within a line (x coords in page image pixels)."""
    word_no: int
    x0: int
    x1: int
    text: str = ""  # filled when PDF has a text-layer; otherwise empty


@dataclass
class LineLayout:
    """A single *true Gemara layout* line band (y coords in page image pixels)."""
    line_no: int
    y0: int
    y1: int
    words: list[WordBox]


@dataclass
class PageLayout:
    masechta: str
    daf: int
    amud: str
    page_image: str
    column_bbox: tuple[int, int, int, int]  # x0,y0,x1,y1 in page image
    lines: list[LineLayout]
    meta: dict[str, Any]

    @property
    def daf_amud(self) -> str:
        return f"{self.daf}{self.amud}"
