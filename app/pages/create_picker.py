from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6 import QtWidgets, QtCore

from ..widgets import Card, TopBar
from ..store import DataStore, Project
from ..daf_engine import ensure_page_layout, PageLayout
from ..models.selection import Selection
from .create_shared import (
    Cursor,
    WordContextView,
    clamp_cursor,
    first_cursor,
    last_cursor,
)


def _parse_daf_amud(txt: str) -> tuple[int, str]:
    txt = (txt or "").strip()
    if not txt:
        return (2, "a")
    return (int(txt[:-1]), txt[-1])


class CreatePickerPage(QtWidgets.QWidget):
    """Page 1/2: pick start page+word and end page+word (range can span pages)."""

    back_to_browse = QtCore.Signal()
    generateRequested = QtCore.Signal(object)  # Selection

    def __init__(self, ds: DataStore, project_root: Path, parent=None):
        super().__init__(parent)
        self.ds = ds
        self.project_root = project_root

        self._project: Optional[Project] = None

        self._start_layout: Optional[PageLayout] = None
        self._end_layout: Optional[PageLayout] = None
        self._start_err: Optional[str] = None
        self._end_err: Optional[str] = None

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(12)

        self.top = TopBar("Create — Picker", show_back=True, show_home=False)
        self.top.back_clicked.connect(self.back_to_browse.emit)
        outer.addWidget(self.top)

        card = Card()
        lay = QtWidgets.QVBoxLayout(card)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(14)

        # -------- row 1: masechta/perek
        row0 = QtWidgets.QHBoxLayout()
        row0.setSpacing(10)
        self.cmb_masechta = QtWidgets.QComboBox()
        self.cmb_masechta.addItems(["Sukkah"])
        self.cmb_perek = QtWidgets.QComboBox()
        self.cmb_perek.addItems(["1"])
        for w in (self.cmb_masechta, self.cmb_perek):
            w.setFixedHeight(34)

        row0.addWidget(QtWidgets.QLabel("Masechta"))
        row0.addWidget(self.cmb_masechta, 2)
        row0.addSpacing(12)
        row0.addWidget(QtWidgets.QLabel("Perek"))
        row0.addWidget(self.cmb_perek, 1)
        row0.addStretch(3)
        lay.addLayout(row0)

        # -------- row 2: start/end page selectors
        row1 = QtWidgets.QGridLayout()
        row1.setHorizontalSpacing(10)
        row1.setVerticalSpacing(8)

        self.cmb_start_daf = QtWidgets.QComboBox()
        self.cmb_end_daf = QtWidgets.QComboBox()
        for w in (self.cmb_start_daf, self.cmb_end_daf):
            w.setFixedHeight(34)
            w.addItems(["2a", "2b", "3a", "3b", "4a", "4b"])

        lbl_start = QtWidgets.QLabel("Start page")
        lbl_end = QtWidgets.QLabel("End page")
        lbl_start.setObjectName("h3")
        lbl_end.setObjectName("h3")

        row1.addWidget(lbl_start, 0, 0)
        row1.addWidget(self.cmb_start_daf, 0, 1)
        row1.addWidget(lbl_end, 0, 2)
        row1.addWidget(self.cmb_end_daf, 0, 3)
        row1.setColumnStretch(1, 1)
        row1.setColumnStretch(3, 1)
        lay.addLayout(row1)

        self.status = QtWidgets.QLabel("Select start page/word → select end page/word → Generate")
        self.status.setObjectName("muted")
        lay.addWidget(self.status)

        # -------- start/end word controls
        self.start_view = WordContextView("Start word")
        self.end_view = WordContextView("End word")
        lay.addWidget(self.start_view)
        lay.addWidget(self.end_view)

        # -------- bottom buttons
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        self.btn_generate = QtWidgets.QPushButton("Generate")
        self.btn_generate.setFixedHeight(40)
        self.btn_generate.setCursor(QtCore.Qt.PointingHandCursor)
        btn_row.addWidget(self.btn_generate)
        lay.addLayout(btn_row)

        outer.addWidget(card)
        outer.addStretch(1)

        # signals
        self.cmb_start_daf.currentTextChanged.connect(lambda _t: self._load_start_layout(reset_cursor=True))
        self.cmb_end_daf.currentTextChanged.connect(lambda _t: self._load_end_layout(reset_cursor=True))
        self.btn_generate.clicked.connect(self._on_generate)

        self.start_view.boundary.connect(lambda d, k: self._on_boundary("start", d, k))
        self.end_view.boundary.connect(lambda d, k: self._on_boundary("end", d, k))

    # ----- public

    def set_project(self, pr: Project) -> None:
        self._project = pr
        self.cmb_masechta.setCurrentText(pr.masechta or "Sukkah")
        self.cmb_perek.setCurrentText(pr.perek or "1")

        # Default: both start/end on the project's daf
        daf_txt = (pr.daf or "2a").strip()
        if daf_txt in [self.cmb_start_daf.itemText(i) for i in range(self.cmb_start_daf.count())]:
            self.cmb_start_daf.setCurrentText(daf_txt)
            self.cmb_end_daf.setCurrentText(daf_txt)
        else:
            self.cmb_start_daf.setCurrentText("2a")
            self.cmb_end_daf.setCurrentText("2a")

        self._load_start_layout(reset_cursor=True)
        self._load_end_layout(reset_cursor=True)

    # ----- internals

    def _load_start_layout(self, reset_cursor: bool) -> None:
        daf, amud = _parse_daf_amud(self.cmb_start_daf.currentText())
        layout, err = ensure_page_layout(self.project_root, masechta=self.cmb_masechta.currentText(), daf=daf, amud=amud)
        self._start_layout = layout
        self._start_err = err
        if err or not layout:
            self.start_view.set_enabled(False)
            self.status.setText(err or "No layout loaded for start page.")
            return
        self.start_view.set_enabled(True)
        if reset_cursor:
            self.start_view.set_layout_and_cursor(layout, first_cursor(layout))
        else:
            self.start_view.set_layout_and_cursor(layout, clamp_cursor(layout, self.start_view.cursor()))
        self.status.setText("Select start page/word → select end page/word → Generate")

    def _load_end_layout(self, reset_cursor: bool) -> None:
        daf, amud = _parse_daf_amud(self.cmb_end_daf.currentText())
        layout, err = ensure_page_layout(self.project_root, masechta=self.cmb_masechta.currentText(), daf=daf, amud=amud)
        self._end_layout = layout
        self._end_err = err
        if err or not layout:
            self.end_view.set_enabled(False)
            self.status.setText(err or "No layout loaded for end page.")
            return
        self.end_view.set_enabled(True)
        if reset_cursor:
            self.end_view.set_layout_and_cursor(layout, last_cursor(layout))
        else:
            self.end_view.set_layout_and_cursor(layout, clamp_cursor(layout, self.end_view.cursor()))
        self.status.setText("Select start page/word → select end page/word → Generate")

    def _on_boundary(self, which: str, delta_page: int, _kind: str) -> None:
        # Move only the side that hit the boundary
        cmb = self.cmb_start_daf if which == "start" else self.cmb_end_daf
        idx = cmb.currentIndex()
        if idx < 0:
            return
        new_idx = idx + (1 if delta_page > 0 else -1)
        if new_idx < 0 or new_idx >= cmb.count():
            return
        cmb.setCurrentIndex(new_idx)
        # layout reload happens via signal, but we want deterministic cursor at edge
        if which == "start" and self._start_layout:
            self.start_view.set_layout_and_cursor(self._start_layout, first_cursor(self._start_layout) if delta_page > 0 else last_cursor(self._start_layout))
        if which == "end" and self._end_layout:
            self.end_view.set_layout_and_cursor(self._end_layout, last_cursor(self._end_layout) if delta_page > 0 else first_cursor(self._end_layout))

    def _on_generate(self) -> None:
        if not self._project:
            return
        if not self._start_layout or not self._end_layout:
            return

        s_daf, s_amud = _parse_daf_amud(self.cmb_start_daf.currentText())
        e_daf, e_amud = _parse_daf_amud(self.cmb_end_daf.currentText())

        s_cur = clamp_cursor(self._start_layout, self.start_view.cursor())
        e_cur = clamp_cursor(self._end_layout, self.end_view.cursor())

        sel = Selection(
            masechta=self.cmb_masechta.currentText(),
            perek=self.cmb_perek.currentText(),
            start_daf=s_daf,
            start_amud=s_amud,
            end_daf=e_daf,
            end_amud=e_amud,
            start_line_i=s_cur.line_i,
            start_word_i=s_cur.word_i,
            end_line_i=e_cur.line_i,
            end_word_i=e_cur.word_i,
        )

        # persist selection seed on project
        self._project.masechta = sel.masechta
        self._project.perek = sel.perek
        self._project.daf = f"{sel.start_daf}{sel.start_amud}"
        self.ds.update_project(self._project)

        self.generateRequested.emit(sel)
