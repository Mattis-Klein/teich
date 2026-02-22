from __future__ import annotations
from PySide6 import QtWidgets, QtCore

from ..widgets import Card, TopBar

class HomePage(QtWidgets.QWidget):
    new_page = QtCore.Signal()
    go_browse = QtCore.Signal()
    go_import = QtCore.Signal()
    go_settings = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(18)

        outer.addWidget(TopBar("Teich"))

        # center 2x2 grid
        center = QtWidgets.QWidget()
        grid = QtWidgets.QGridLayout(center)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(18)

        def big_btn(text: str) -> QtWidgets.QPushButton:
            b = QtWidgets.QPushButton(text)
            b.setFixedSize(200, 200)
            b.setCursor(QtCore.Qt.PointingHandCursor)
            b.setObjectName("bigSquare")
            return b

        b_new = big_btn("New Page")
        b_browse = big_btn("Browse")
        b_import = big_btn("Import")
        b_settings = big_btn("Settings")

        grid.addWidget(b_new, 0, 0)
        grid.addWidget(b_browse, 0, 1)
        grid.addWidget(b_import, 1, 0)
        grid.addWidget(b_settings, 1, 1)

        outer.addStretch(1)
        outer.addWidget(center, alignment=QtCore.Qt.AlignCenter)
        outer.addStretch(2)

        b_new.clicked.connect(self.new_page.emit)
        b_browse.clicked.connect(self.go_browse.emit)
        b_import.clicked.connect(self.go_import.emit)
        b_settings.clicked.connect(self.go_settings.emit)
