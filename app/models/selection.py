from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Selection:
    """A pure-JSON-able contract for Create flow navigation (Picker -> Editor)."""

    masechta: str
    perek: str
    # Range can span pages (start page != end page)
    start_daf: int
    start_amud: str  # "a" | "b"
    end_daf: int
    end_amud: str  # "a" | "b"

    start_line_i: int
    start_word_i: int
    end_line_i: int
    end_word_i: int
