from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from PySide6 import QtCore, QtWidgets

from ..daf_engine.model import PageLayout


@dataclass
class Cursor:
    line_i: int
    word_i: int


def clamp_cursor(layout: PageLayout, cur: Cursor) -> Cursor:
    li = max(0, min(cur.line_i, max(0, len(layout.lines) - 1)))
    ln = layout.lines[li] if layout.lines else None
    if not ln or not ln.words:
        return Cursor(0, 0)
    wi = max(0, min(cur.word_i, max(0, len(ln.words) - 1)))
    return Cursor(li, wi)


def first_cursor(layout: PageLayout) -> Cursor:
    for li, ln in enumerate(layout.lines):
        if ln.words:
            return Cursor(li, 0)
    return Cursor(0, 0)


def last_cursor(layout: PageLayout) -> Cursor:
    for li in range(len(layout.lines) - 1, -1, -1):
        ln = layout.lines[li]
        if ln.words:
            return Cursor(li, len(ln.words) - 1)
    return Cursor(0, 0)


def cursor_leq(a: Cursor, b: Cursor) -> bool:
    return (a.line_i, a.word_i) <= (b.line_i, b.word_i)


def extract_words_in_range(layout: PageLayout, start: Cursor, end: Cursor) -> List[str]:
    """Inclusive range by layout cursor; returns stripped non-empty tokens."""
    start = clamp_cursor(layout, start)
    end = clamp_cursor(layout, end)

    words: List[str] = []
    in_range = False
    for li, ln in enumerate(layout.lines):
        for wi, wb in enumerate(ln.words):
            cur = Cursor(li, wi)
            if (cur.line_i, cur.word_i) == (start.line_i, start.word_i):
                in_range = True
            if in_range:
                t = (wb.text or "").strip()
                if t:
                    words.append(t)
            if (cur.line_i, cur.word_i) == (end.line_i, end.word_i):
                in_range = False
                break
        if not in_range and li > end.line_i:
            break
    return words


class WordContextView(QtWidgets.QWidget):
    """Shows 5-word context around the active word, with the active word highlighted."""

    moved = QtCore.Signal()  # emitted when cursor changes
    boundary = QtCore.Signal(int, str)  # (delta_page, kind) when moving past page edges

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self._layout: Optional[PageLayout] = None
        self._cursor = Cursor(0, 0)
        self._enabled = True

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)

        hdr = QtWidgets.QHBoxLayout()
        lbl = QtWidgets.QLabel(title)
        lbl.setObjectName("h3")
        hdr.addWidget(lbl)
        hdr.addStretch(1)

        self.pos_label = QtWidgets.QLabel("—")
        # keep dark/prominent (user requested)
        self.pos_label.setObjectName("")
        hdr.addWidget(self.pos_label)
        outer.addLayout(hdr)

        nav = QtWidgets.QHBoxLayout()
        nav.setSpacing(8)

        self.btn_prev_line = QtWidgets.QPushButton("◀ Line")
        self.btn_prev_word = QtWidgets.QPushButton("◀ Word")
        self.btn_next_word = QtWidgets.QPushButton("Word ▶")
        self.btn_next_line = QtWidgets.QPushButton("Line ▶")
        for b in (self.btn_prev_line, self.btn_prev_word, self.btn_next_word, self.btn_next_line):
            b.setFixedHeight(34)
            b.setCursor(QtCore.Qt.PointingHandCursor)

        nav.addWidget(self.btn_prev_line)
        nav.addWidget(self.btn_prev_word)

        nav.addStretch(1)

        self.context = QtWidgets.QLabel("—")
        self.context.setTextFormat(QtCore.Qt.RichText)
        self.context.setAlignment(QtCore.Qt.AlignCenter)
        self.context.setMinimumHeight(42)
        self.context.setObjectName("contextLine")
        nav.addWidget(self.context, 6)

        nav.addStretch(1)

        nav.addWidget(self.btn_next_word)
        nav.addWidget(self.btn_next_line)
        outer.addLayout(nav)

        self.btn_prev_word.clicked.connect(lambda: self._step_word(-1))
        self.btn_next_word.clicked.connect(lambda: self._step_word(+1))
        self.btn_prev_line.clicked.connect(lambda: self._step_line(-1))
        self.btn_next_line.clicked.connect(lambda: self._step_line(+1))

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        for b in (self.btn_prev_line, self.btn_prev_word, self.btn_next_word, self.btn_next_line):
            b.setEnabled(enabled)
        self._render()

    def set_layout_and_cursor(self, layout: Optional[PageLayout], cursor: Cursor) -> None:
        self._layout = layout
        self._cursor = cursor
        self._render()

    def cursor(self) -> Cursor:
        return self._cursor

    def _step_word(self, delta: int) -> None:
        if not self._enabled or not self._layout:
            return

        cur = clamp_cursor(self._layout, self._cursor)
        ln = self._layout.lines[cur.line_i]
        wi = cur.word_i + delta
        li = cur.line_i

        while True:
            if 0 <= wi < len(ln.words):
                self._cursor = Cursor(li, wi)
                self._render()
                self.moved.emit()
                return

            if delta > 0:
                li += 1
                if li >= len(self._layout.lines):
                    self.boundary.emit(+1, "word")
                    return
                ln = self._layout.lines[li]
                wi = 0
            else:
                li -= 1
                if li < 0:
                    self.boundary.emit(-1, "word")
                    return
                ln = self._layout.lines[li]
                wi = max(0, len(ln.words) - 1)

    def _step_line(self, delta: int) -> None:
        if not self._enabled or not self._layout:
            return

        cur = clamp_cursor(self._layout, self._cursor)

        if delta < 0 and cur.line_i == 0:
            self.boundary.emit(-1, "line")
            return
        if delta > 0 and cur.line_i >= len(self._layout.lines) - 1:
            self.boundary.emit(+1, "line")
            return

        li = max(0, min(cur.line_i + delta, len(self._layout.lines) - 1))
        ln = self._layout.lines[li]
        wi = min(cur.word_i, max(0, len(ln.words) - 1))
        self._cursor = Cursor(li, wi)
        self._render()
        self.moved.emit()

    @staticmethod
    def _esc(s: str) -> str:
        return (
            (s or "")
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    def _render(self) -> None:
        if not self._layout or not self._layout.lines:
            self.pos_label.setText("—")
            self.context.setText("—")
            return

        cur = clamp_cursor(self._layout, self._cursor)
        ln = self._layout.lines[cur.line_i]

        # position label
        self.pos_label.setText(f"L{ln.line_no}:W{cur.word_i + 1}")

        words_in_line = [(w.text or "") for w in ln.words]
        i = cur.word_i

        ctx = []
        for j in range(i - 2, i + 3):
            ctx.append(words_in_line[j] if 0 <= j < len(words_in_line) else "")

        parts = []
        for k, t in enumerate(ctx):
            t = self._esc(t) if t else "&nbsp;"
            if k == 2:
                # ✅ active word highlighted
                parts.append(f"<b>{t}</b>")
            else:
                parts.append(t)

        self.context.setText(" ".join(parts))
