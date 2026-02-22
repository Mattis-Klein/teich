from __future__ import annotations
from PySide6 import QtWidgets, QtCore

class Card(QtWidgets.QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("class", "Card")
        self.setObjectName("CardFrame")
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.setContentsMargins(0,0,0,0)
        self.setStyleSheet("QFrame { }")  # keep for property-based styling

class TopBar(QtWidgets.QFrame):
    back_clicked = QtCore.Signal()
    home_clicked = QtCore.Signal()

    def __init__(self, title: str, show_back: bool = True, parent=None):
        super().__init__(parent)
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 10)
        lay.setSpacing(10)

        self.btn_back = QtWidgets.QPushButton("← Back")
        self.btn_back.setVisible(show_back)
        self.btn_back.clicked.connect(self.back_clicked.emit)

        self.btn_home = QtWidgets.QPushButton("⌂ Home")
        self.btn_home.clicked.connect(self.home_clicked.emit)

        self.lbl = QtWidgets.QLabel(title)
        self.lbl.setObjectName("PageTitle")
        self.lbl.setAlignment(QtCore.Qt.AlignCenter)

        lay.addWidget(self.btn_back, 0, QtCore.Qt.AlignLeft)
        lay.addWidget(self.btn_home, 0, QtCore.Qt.AlignLeft)
        lay.addStretch(1)
        lay.addWidget(self.lbl, 0, QtCore.Qt.AlignCenter)
        lay.addStretch(1)
        lay.addSpacing(10)

class PlaceholderPage(QtWidgets.QWidget):
    def __init__(self, title: str, message: str, parent=None):
        super().__init__(parent)
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(22, 10, 22, 22)
        outer.setSpacing(14)

        self.top = TopBar(title, show_back=True)
        outer.addWidget(self.top)

        outer.addStretch(1)
        card = Card()
        card.setProperty("class", "Card")
        card_l = QtWidgets.QVBoxLayout(card)
        card_l.setContentsMargins(18, 18, 18, 18)
        card_l.setSpacing(10)

        lbl = QtWidgets.QLabel(message)
        lbl.setAlignment(QtCore.Qt.AlignCenter)
        lbl.setWordWrap(True)
        lbl.setStyleSheet("QLabel { font-size: 14pt; }")
        card_l.addWidget(lbl)

        outer.addWidget(card, 0, QtCore.Qt.AlignHCenter)
        card.setFixedWidth(520)
        outer.addStretch(2)

        self.card = card
