from __future__ import annotations
import re

_HEBREW_NIKUD_RE = re.compile(r"[\u0591-\u05C7]")  # cantillation + vowel points
_PUNCT_RE = re.compile(r"[\s\.,;:!?\-\u05BE\u05F3\u05F4\"'“”‘’()\[\]{}<>/\\]+")

def strip_nikud(s: str) -> str:
    return _HEBREW_NIKUD_RE.sub("", s or "")

def normalize_token(s: str) -> str:
    """
    Normalization for search:
    - remove nikud
    - remove punctuation/spaces
    - keep Hebrew letters/numbers (simple)
    """
    s = strip_nikud(s)
    s = _PUNCT_RE.sub("", s)
    return s
