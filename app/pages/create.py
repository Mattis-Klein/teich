from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple, List

from PySide6 import QtWidgets, QtCore

from ..widgets import Card, TopBar
from ..store import DataStore, Project
from ..daf_engine import ensure_page_layout, PageLayout


@dataclass
class Cursor:
    line_i: int
    word_i: int


def _flatten_words(layout: PageLayout) -> List[str]:
    out: List[str] = []
    for ln in layout.lines:
        for w in ln.words:
            out.append(w.text or "")
    return out


def _cursor_to_flat_index(layout: PageLayout, cur: Cursor) -> int:
    idx = 0
    for li, ln in enumerate(layout.lines):
        if li < cur.line_i:
            idx += len(ln.words)
        elif li == cur.line_i:
            idx += min(cur.word_i, max(0, len(ln.words) - 1))
            return idx
    return max(0, idx - 1)


def _clamp_cursor(layout: PageLayout, cur: Cursor) -> Cursor:
    li = max(0, min(cur.line_i, max(0, len(layout.lines) - 1)))
    ln = layout.lines[li] if layout.lines else None
    if not ln or not ln.words:
        return Cursor(0, 0)
    wi = max(0, min(cur.word_i, max(0, len(ln.words) - 1)))
    return Cursor(li, wi)


def _first_cursor(layout: PageLayout) -> Cursor:
    for li, ln in enumerate(layout.lines):
        if ln.words:
            return Cursor(li, 0)
    return Cursor(0, 0)


def _last_cursor(layout: PageLayout) -> Cursor:
    for li in range(len(layout.lines) - 1, -1, -1):
        ln = layout.lines[li]
        if ln.words:
            return Cursor(li, len(ln.words) - 1)
    return Cursor(0, 0)


def _cursor_leq(a: Cursor, b: Cursor) -> bool:
    return (a.line_i, a.word_i) <= (b.line_i, b.word_i)


class WordContextView(QtWidgets.QWidget):
    """Shows 5-word context around the active word, and a stable position label."""

    moved = QtCore.Signal()  # emitted when cursor changes

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
        self.pos_label.setObjectName("muted")
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
        cur = _clamp_cursor(self._layout, self._cursor)
        ln = self._layout.lines[cur.line_i]
        wi = cur.word_i + delta
        li = cur.line_i
        # step across lines
        while True:
            if 0 <= wi < len(ln.words):
                self._cursor = Cursor(li, wi)
                self._render()
                self.moved.emit()
                return
            if delta > 0:
                li += 1
                if li >= len(self._layout.lines):
                    li = len(self._layout.lines) - 1
                    ln = self._layout.lines[li]
                    self._cursor = Cursor(li, max(0, len(ln.words) - 1))
                    self._render()
                    self.moved.emit()
                    return
                ln = self._layout.lines[li]
                wi = 0
            else:
                li -= 1
                if li < 0:
                    li = 0
                    ln = self._layout.lines[li]
                    self._cursor = Cursor(li, 0)
                    self._render()
                    self.moved.emit()
                    return
                ln = self._layout.lines[li]
                wi = max(0, len(ln.words) - 1)

    def _step_line(self, delta: int) -> None:
        if not self._enabled or not self._layout:
            return
        cur = _clamp_cursor(self._layout, self._cursor)
        li = max(0, min(cur.line_i + delta, len(self._layout.lines) - 1))
        ln = self._layout.lines[li]
        wi = min(cur.word_i, max(0, len(ln.words) - 1))
        self._cursor = Cursor(li, wi)
        self._render()
        self.moved.emit()

    def _render(self) -> None:
        if not self._layout or not self._layout.lines:
            self.pos_label.setText("—")
            self.context.setText("—")
            return

        cur = _clamp_cursor(self._layout, self._cursor)
        ln = self._layout.lines[cur.line_i]
        word = ln.words[cur.word_i].text or ""

        # position label
        self.pos_label.setText(f"L{ln.line_no}:W{cur.word_i + 1}")

        # 5-word context: 2 before, active, 2 after (same line if possible, else blanks)
        words_in_line = [w.text or "" for w in ln.words]
        i = cur.word_i
        ctx = []
        for j in range(i - 2, i + 3):
            if 0 <= j < len(words_in_line):
                t = words_in_line[j] or ""
            else:
                t = ""
            ctx.append(t)

        # Highlight the active word (center)
        def esc(s: str) -> str:
            return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

        parts = []
        for k, t in enumerate(ctx):
            t = esc(t) if t else "&nbsp;"
            if k == 2:
                parts.append(f"<span class='activeWord'>{t}</span>")
            else:
                parts.append(f"<span class='ctxWord'>{t}</span>")
        self.context.setText(" ".join(parts))


class CreatePage(QtWidgets.QWidget):
    back = QtCore.Signal()
    saved = QtCore.Signal()  # emitted when project changes

    def __init__(self, ds: DataStore, project_root: Path, parent=None):
        super().__init__(parent)
        self.ds = ds
        self.project_root = project_root

        self._project: Optional[Project] = None
        self._layout: Optional[PageLayout] = None
        self._layout_error: Optional[str] = None

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(12)

        self.top = TopBar("Create")
        self.top.back_clicked.connect(self.back.emit)
        outer.addWidget(self.top)

        # --- Selection card (full width)
        self.sel_card = Card()
        sel = QtWidgets.QVBoxLayout(self.sel_card)
        sel.setContentsMargins(14, 14, 14, 14)
        sel.setSpacing(10)

        # Step row: Masechta / Perek / Daf-Amud
        row1 = QtWidgets.QHBoxLayout()
        row1.setSpacing(10)

        self.cmb_masechta = QtWidgets.QComboBox()
        self.cmb_masechta.addItems(["Sukkah"])
        self.cmb_perek = QtWidgets.QComboBox()
        self.cmb_perek.addItems(["1"])
        self.cmb_daf = QtWidgets.QComboBox()
        self.cmb_daf.addItems(["2a", "2b", "3a", "3b", "4a"])

        for w in (self.cmb_masechta, self.cmb_perek, self.cmb_daf):
            w.setFixedHeight(34)

        row1.addWidget(QtWidgets.QLabel("Masechta"))
        row1.addWidget(self.cmb_masechta, 1)
        row1.addSpacing(10)
        row1.addWidget(QtWidgets.QLabel("Perek"))
        row1.addWidget(self.cmb_perek, 1)
        row1.addSpacing(10)
        row1.addWidget(QtWidgets.QLabel("Daf/Amud"))
        row1.addWidget(self.cmb_daf, 1)
        row1.addStretch(1)

        sel.addLayout(row1)

        self.status = QtWidgets.QLabel("Select Masechta → Perek → Daf/Amud")
        self.status.setObjectName("muted")
        sel.addWidget(self.status)

        self.start_view = WordContextView("Start word")
        self.end_view = WordContextView("End word")
        sel.addWidget(self.start_view)
        sel.addWidget(self.end_view)

        self.btn_generate = QtWidgets.QPushButton("Generate")
        self.btn_generate.setFixedHeight(40)
        self.btn_generate.setCursor(QtCore.Qt.PointingHandCursor)
        sel.addWidget(self.btn_generate, alignment=QtCore.Qt.AlignLeft)

        outer.addWidget(self.sel_card)

        # --- Table (word | explanation)
        self.table_card = Card()
        tlay = QtWidgets.QVBoxLayout(self.table_card)
        tlay.setContentsMargins(0, 0, 0, 0)

        self.table = QtWidgets.QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Word", "Explanation"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.DoubleClicked | QtWidgets.QAbstractItemView.EditKeyPressed)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(True)
        self.table.setObjectName("mainTable")

        self.table.setColumnWidth(0, 220)

        tlay.addWidget(self.table)
        outer.addWidget(self.table_card, 1)

        # signals
        self.cmb_daf.currentTextChanged.connect(self._on_daf_changed)
        self.btn_generate.clicked.connect(self._on_generate)

        # whenever start moves, keep end >= start
        self.start_view.moved.connect(self._ensure_order)
        self.end_view.moved.connect(self._ensure_order)

    def set_project(self, pr: Project) -> None:
        self._project = pr
        # Load any prior rows
        self._reload_table_from_project()
        # set selection widgets from project metadata
        self.cmb_masechta.setCurrentText(pr.masechta or "Sukkah")
        self.cmb_perek.setCurrentText(pr.perek or "1")
        self.cmb_daf.setCurrentText(pr.daf or "2a")
        self._load_layout_for_current_daf(reset_start_end=True)

    # ---------- internal UI logic

    def _on_daf_changed(self, _txt: str) -> None:
        # Predictable: reset to first+last word when Daf/Amud changes.
        self._load_layout_for_current_daf(reset_start_end=True)

    def _pdf_for_daf(self, daf_amud: str) -> Path:
        key = f"sukkah_{daf_amud}.pdf"
        return self.project_root / "data" / "pdfs" / key

    def _load_layout_for_current_daf(self, reset_start_end: bool) -> None:
        daf_amud = self.cmb_daf.currentText().strip()
        if not daf_amud:
            return

        daf = int(daf_amud[:-1])
        amud = daf_amud[-1]

        pdf_path = self._pdf_for_daf(daf_amud)
        if not pdf_path.exists():
            self._layout = None
            self._layout_error = f"Missing PDF: {pdf_path.name}"
            self._apply_layout_state()
            return

        layout, err = ensure_page_layout(
            self.project_root,
            masechta=self.cmb_masechta.currentText(),
            daf=daf,
            amud=amud,
            pdf_path=pdf_path,
        )
        self._layout = layout
        self._layout_error = err
        self._apply_layout_state()

        if layout and reset_start_end:
            self.start_view.set_layout_and_cursor(layout, _first_cursor(layout))
            self.end_view.set_layout_and_cursor(layout, _last_cursor(layout))
            self._ensure_order()

        # update project fields
        if self._project:
            self._project.masechta = self.cmb_masechta.currentText()
            self._project.perek = self.cmb_perek.currentText()
            self._project.daf = daf_amud
            self.ds.update_project(self._project)

    def _apply_layout_state(self) -> None:
        if self._layout_error:
            self.status.setText(self._layout_error)
        elif not self._layout:
            self.status.setText("No layout loaded.")
        else:
            has_text = bool(self._layout.meta.get("has_textlayer"))
            if has_text:
                self.status.setText("Select Start word → Select End word → Press Generate")
            else:
                self.status.setText("This PDF appears to be image-only (no selectable text). Word-based selection needs OCR.")
        enabled = bool(self._layout) and bool(self._layout.meta.get("has_textlayer"))
        self.start_view.set_enabled(enabled)
        self.end_view.set_enabled(enabled)
        self.btn_generate.setEnabled(enabled)

    def _ensure_order(self) -> None:
        if not self._layout:
            return
        a = _clamp_cursor(self._layout, self.start_view.cursor())
        b = _clamp_cursor(self._layout, self.end_view.cursor())
        if not _cursor_leq(a, b):
            # If user moved start beyond end, snap end to start (predictable).
            self.end_view.set_layout_and_cursor(self._layout, a)

    def _on_generate(self) -> None:
        if not self._layout or not self._project:
            return
        if not self._layout.meta.get("has_textlayer"):
            return

        start = _clamp_cursor(self._layout, self.start_view.cursor())
        end = _clamp_cursor(self._layout, self.end_view.cursor())

        # Flatten words with their cursors
        words: List[str] = []
        in_range = False
        for li, ln in enumerate(self._layout.lines):
            for wi, wb in enumerate(ln.words):
                cur = Cursor(li, wi)
                if cur.line_i == start.line_i and cur.word_i == start.word_i:
                    in_range = True
                if in_range:
                    t = wb.text.strip()
                    if t:
                        words.append(t)
                if cur.line_i == end.line_i and cur.word_i == end.word_i:
                    in_range = False
                    break
            if not in_range and (li > end.line_i):
                break

        # Insert into table: one row per word, explanation empty.
        for w in words:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QtWidgets.QTableWidgetItem(w))
            self.table.setItem(r, 1, QtWidgets.QTableWidgetItem(""))

        self._sync_project_from_table()
        self.saved.emit()

    def _reload_table_from_project(self) -> None:
        self.table.setRowCount(0)
        if not self._project:
            return
        rows = self._project.rows or []
        for row in rows:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QtWidgets.QTableWidgetItem(row.get("word", "")))
            self.table.setItem(r, 1, QtWidgets.QTableWidgetItem(row.get("explanation", "")))

    def _sync_project_from_table(self) -> None:
        if not self._project:
            return
        rows = []
        for r in range(self.table.rowCount()):
            w = self.table.item(r, 0).text() if self.table.item(r, 0) else ""
            e = self.table.item(r, 1).text() if self.table.item(r, 1) else ""
            rows.append({"word": w, "explanation": e})
        self._project.rows = rows
        self.ds.update_project(self._project)
