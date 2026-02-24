from __future__ import annotations

from typing import List, Optional

from PySide6 import QtWidgets, QtCore

from .store import WordEntry


class MatchPickerDialog(QtWidgets.QDialog):
    """Pick a stored explanation for a clicked word."""

    def __init__(self, word_text: str, matches: List[WordEntry], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Choose explanation")
        self.setModal(True)

        self.selected: Optional[WordEntry] = None
        self._matches = matches

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(14, 14, 14, 14)
        outer.setSpacing(10)

        hdr = QtWidgets.QLabel(f"Word: {word_text}")
        hdr.setObjectName("h3")
        outer.addWidget(hdr)

        self.list = QtWidgets.QListWidget()
        self.list.setAlternatingRowColors(True)
        outer.addWidget(self.list, 1)

        for m in matches:
            expl = (m.english or "").strip()
            src = ", ".join(m.sources or [])
            label = expl if expl else "(empty)"
            if src:
                label = f"{label}    —    {src}"
            self.list.addItem(label)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)

        self.btn_use = QtWidgets.QPushButton("Use selected")
        self.btn_use.setCursor(QtCore.Qt.PointingHandCursor)
        btn_row.addWidget(self.btn_use)

        outer.addLayout(btn_row)

        self.btn_use.clicked.connect(self._accept_selected)
        self.list.itemDoubleClicked.connect(lambda *_: self._accept_selected())

        self.resize(820, 420)

    def _accept_selected(self):
        idx = self.list.currentRow()
        if idx < 0:
            return
        self.selected = self._matches[idx]
        self.accept()
