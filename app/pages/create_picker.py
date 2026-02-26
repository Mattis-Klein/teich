from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

from PySide6 import QtCore, QtWidgets

from ..daf_engine import PageLayout, ensure_page_layout
from ..models.selection import Selection
from ..store import DataStore, Project
from ..widgets import Card, TopBar
from .create_shared import (
    Cursor,
    WordContextView,
    clamp_cursor,
    cursor_leq,
    first_cursor,
    last_cursor,
)


def _parse_daf_amud(txt: str) -> Tuple[int, str]:
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

        # When paging via boundary, we want deterministic line behavior
        self._pending_start_edge: Optional[str] = None  # "first"|"last"|None
        self._pending_end_edge: Optional[str] = None

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(12)

        self.top = TopBar("Range Picker", show_back=True, show_home=False)
        self.top.back_clicked.connect(self.back_to_browse.emit)
        outer.addWidget(self.top)

        card = Card()
        lay = QtWidgets.QVBoxLayout(card)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(14)

        # Row 1: masechta/perek
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

        # Row 2: start/end page selectors
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

        # Start/end word controls
        self.start_view = WordContextView("Start word")
        self.end_view = WordContextView("End word")
        lay.addWidget(self.start_view)
        lay.addWidget(self.end_view)

        # Bottom
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        self.btn_generate = QtWidgets.QPushButton("Generate")
        self.btn_generate.setFixedHeight(40)
        self.btn_generate.setCursor(QtCore.Qt.PointingHandCursor)
        btn_row.addWidget(self.btn_generate)
        lay.addLayout(btn_row)

        outer.addWidget(card)
        outer.addStretch(1)

        # Signals
        self.cmb_start_daf.currentIndexChanged.connect(lambda _i: self._on_start_page_changed())
        self.cmb_end_daf.currentIndexChanged.connect(lambda _i: self._on_end_page_changed())

        self.btn_generate.clicked.connect(self._on_generate)

        self.start_view.boundary.connect(lambda d, k: self._on_boundary("start", d, k))
        self.end_view.boundary.connect(lambda d, k: self._on_boundary("end", d, k))
        self.start_view.moved.connect(lambda: self._enforce_constraints(changed="start"))
        self.end_view.moved.connect(lambda: self._enforce_constraints(changed="end"))

    # ----- public
    def set_project(self, pr: Project) -> None:
        self._project = pr
        self.cmb_masechta.setCurrentText(pr.masechta or "Sukkah")
        self.cmb_perek.setCurrentText(pr.perek or "1")

        daf_txt = (pr.daf or "2a").strip()
        items = [self.cmb_start_daf.itemText(i) for i in range(self.cmb_start_daf.count())]
        if daf_txt in items:
            self.cmb_start_daf.setCurrentText(daf_txt)
            self.cmb_end_daf.setCurrentText(daf_txt)
        else:
            self.cmb_start_daf.setCurrentText("2a")
            self.cmb_end_daf.setCurrentText("2a")

        self._load_start_layout(reset_cursor=True)
        self._load_end_layout(reset_cursor=True)
        self._enforce_constraints(changed="start")

    # ----- page ordering
    def _on_start_page_changed(self) -> None:
        # If start moved after end, move end to match start.
        if self.cmb_end_daf.currentIndex() < self.cmb_start_daf.currentIndex():
            self.cmb_end_daf.setCurrentIndex(self.cmb_start_daf.currentIndex())
            # end layout reload will trigger via signal; we still load start now
        self._load_start_layout(reset_cursor=True)
        self._enforce_constraints(changed="start")

    def _on_end_page_changed(self) -> None:
        # If end moved before start, move start to match end.
        if self.cmb_start_daf.currentIndex() > self.cmb_end_daf.currentIndex():
            self.cmb_start_daf.setCurrentIndex(self.cmb_end_daf.currentIndex())
        self._load_end_layout(reset_cursor=True)
        self._enforce_constraints(changed="end")

    # ----- layout loaders
    def _load_start_layout(self, reset_cursor: bool) -> None:
        daf, amud = _parse_daf_amud(self.cmb_start_daf.currentText())
        layout, err = ensure_page_layout(
            self.project_root, masechta=self.cmb_masechta.currentText(), daf=daf, amud=amud
        )
        self._start_layout = layout
        self._start_err = err

        if err or not layout:
            self.start_view.set_enabled(False)
            self.status.setText(err or "No layout loaded for start page.")
            return

        self.start_view.set_enabled(True)

        if self._pending_start_edge and layout:
            cur = first_cursor(layout) if self._pending_start_edge == "first" else last_cursor(layout)
            self._pending_start_edge = None
            self.start_view.set_layout_and_cursor(layout, cur)
        else:
            if reset_cursor:
                self.start_view.set_layout_and_cursor(layout, first_cursor(layout))
            else:
                self.start_view.set_layout_and_cursor(layout, clamp_cursor(layout, self.start_view.cursor()))

        self.status.setText("Select start page/word → select end page/word → Generate")

    def _load_end_layout(self, reset_cursor: bool) -> None:
        daf, amud = _parse_daf_amud(self.cmb_end_daf.currentText())
        layout, err = ensure_page_layout(
            self.project_root, masechta=self.cmb_masechta.currentText(), daf=daf, amud=amud
        )
        self._end_layout = layout
        self._end_err = err

        if err or not layout:
            self.end_view.set_enabled(False)
            self.status.setText(err or "No layout loaded for end page.")
            return

        self.end_view.set_enabled(True)

        if self._pending_end_edge and layout:
            cur = first_cursor(layout) if self._pending_end_edge == "first" else last_cursor(layout)
            self._pending_end_edge = None
            self.end_view.set_layout_and_cursor(layout, cur)
        else:
            if reset_cursor:
                self.end_view.set_layout_and_cursor(layout, last_cursor(layout))
            else:
                self.end_view.set_layout_and_cursor(layout, clamp_cursor(layout, self.end_view.cursor()))

        self.status.setText("Select start page/word → select end page/word → Generate")

    # ----- constraints
    def _enforce_constraints(self, changed: str) -> None:
        """Enforce:
        - end page cannot be before start page (already handled by combo changes)
        - within same page: start cannot be after end
        - start cannot pass end-1 word (must keep at least one word gap)
        """
        if not (self._start_layout and self._end_layout):
            return

        s_page = self.cmb_start_daf.currentIndex()
        e_page = self.cmb_end_daf.currentIndex()

        # If pages same, enforce cursor ordering and min gap
        if s_page == e_page:
            s_cur = clamp_cursor(self._start_layout, self.start_view.cursor())
            e_cur = clamp_cursor(self._end_layout, self.end_view.cursor())

            # If start > end, pull the other side to match (depending on which changed)
            if not cursor_leq(s_cur, e_cur):
                if changed == "start":
                    # move end to start
                    self.end_view.set_layout_and_cursor(self._end_layout, s_cur)
                    e_cur = s_cur
                else:
                    self.start_view.set_layout_and_cursor(self._start_layout, e_cur)
                    s_cur = e_cur

            # Now enforce: start <= end-1 word (at least one word gap)
            # Only meaningful if same line; across lines we allow.
            if s_cur.line_i == e_cur.line_i:
                if s_cur.word_i >= max(0, e_cur.word_i - 1):
                    if changed == "start":
                        # clamp start back to end-1 (or 0)
                        new_w = max(0, e_cur.word_i - 1)
                        self.start_view.set_layout_and_cursor(self._start_layout, Cursor(s_cur.line_i, new_w))
                    else:
                        # clamp end forward to start+1
                        new_w = min(e_cur.word_i + 1, len(self._end_layout.lines[e_cur.line_i].words) - 1)
                        if new_w <= s_cur.word_i:
                            new_w = min(s_cur.word_i + 1, len(self._end_layout.lines[e_cur.line_i].words) - 1)
                        self.end_view.set_layout_and_cursor(self._end_layout, Cursor(e_cur.line_i, new_w))

    # ----- boundary paging
    def _on_boundary(self, which: str, delta_page: int, kind: str) -> None:
        """When stepping off page edges, change daf combo and force deterministic cursor:
        - for line +1 at last line: next page, FIRST line
        - for line -1 at first line: prev page, LAST line
        - for word paging: next page -> first word; prev page -> last word
        """
        cmb = self.cmb_start_daf if which == "start" else self.cmb_end_daf
        idx = cmb.currentIndex()
        if idx < 0:
            return
        new_idx = idx + (1 if delta_page > 0 else -1)
        if new_idx < 0 or new_idx >= cmb.count():
            return

        # Decide where cursor should land on the NEW page
        if kind == "line":
            edge = "first" if delta_page > 0 else "last"
        else:
            edge = "first" if delta_page > 0 else "last"

        if which == "start":
            self._pending_start_edge = edge
            cmb.setCurrentIndex(new_idx)  # triggers _on_start_page_changed -> loads layout
            self._load_start_layout(reset_cursor=False)
            self._enforce_constraints(changed="start")
        else:
            self._pending_end_edge = edge
            cmb.setCurrentIndex(new_idx)
            self._load_end_layout(reset_cursor=False)
            self._enforce_constraints(changed="end")

    def _on_generate(self) -> None:
        if not self._project:
            return
        if not self._start_layout or not self._end_layout:
            return

        s_daf, s_amud = _parse_daf_amud(self.cmb_start_daf.currentText())
        e_daf, e_amud = _parse_daf_amud(self.cmb_end_daf.currentText())

        s_cur = clamp_cursor(self._start_layout, self.start_view.cursor())
        e_cur = clamp_cursor(self._end_layout, self.end_view.cursor())

        # Final ordering safety: keep end >= start
        if self.cmb_end_daf.currentIndex() < self.cmb_start_daf.currentIndex():
            self.cmb_end_daf.setCurrentIndex(self.cmb_start_daf.currentIndex())
            self._load_end_layout(reset_cursor=True)
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

        # Persist selection seed on project
        self._project.masechta = sel.masechta
        self._project.perek = sel.perek
        self._project.daf = f"{sel.start_daf}{sel.start_amud}"
        self.ds.update_project(self._project)

        self.generateRequested.emit(sel)
