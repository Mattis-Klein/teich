from __future__ import annotations

def app_stylesheet() -> str:
    # Subtle light-blue vertical gradient, consistent across all pages.
    # Keep borders crisp and avoid heavy shadows.
    return r"""
    /* -------- Global -------- */
    * {
        font-family: "Segoe UI", Arial, sans-serif;
        font-size: 12pt;
    }

    QWidget#AppRoot {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                    stop:0 #eaf4ff,
                                    stop:1 #d7ecff);
        color: #0b1b2b;
    }

    QLabel#PageTitle {
        font-size: 18pt;
        font-weight: 700;
    }

    /* Cards */
    QFrame.Card {
        background: rgba(255,255,255,0.82);
        border: 1px solid rgba(10,40,70,0.20);
        border-radius: 14px;
    }

    /* Buttons */
    QPushButton {
        background: rgba(255,255,255,0.85);
        border: 1px solid rgba(10,40,70,0.22);
        border-radius: 12px;
        padding: 10px 14px;
    }
    QPushButton:hover { background: rgba(255,255,255,0.95); }
    QPushButton:pressed { background: rgba(220,240,255,0.95); }

    QPushButton.Primary {
        background: rgba(15,110,180,0.12);
        border: 1px solid rgba(15,110,180,0.35);
        font-weight: 700;
    }
    QPushButton.Primary:hover { background: rgba(15,110,180,0.16); }

    /* Square buttons on Home */
    QPushButton.HomeTile {
        min-width: 190px;
        min-height: 190px;
        font-size: 16pt;
        font-weight: 700;
        border-radius: 18px;
        background: rgba(255,255,255,0.86);
    }

    /* Inputs */
    QLineEdit, QComboBox, QSpinBox {
        background: rgba(255,255,255,0.90);
        border: 1px solid rgba(10,40,70,0.22);
        border-radius: 10px;
        padding: 8px 10px;
    }

    /* Table */
    QTableWidget {
        background: rgba(255,255,255,0.88);
        border: 1px solid rgba(10,40,70,0.20);
        border-radius: 12px;
        gridline-color: rgba(10,40,70,0.25);
    }
    QHeaderView::section {
        background: rgba(235,248,255,0.95);
        border: none;
        padding: 8px 10px;
        font-weight: 700;
    }

    /* Dark vertical divider requested */
    QFrame#DarkDivider {
        background: rgba(10,40,70,0.55);
        min-width: 2px;
        max-width: 2px;
    }

    /* Segmented toggle */
    QPushButton.Seg {
        border-radius: 10px;
        padding: 8px 10px;
        min-width: 120px;
    }
    QPushButton.SegChecked {
        background: rgba(15,110,180,0.15);
        border: 1px solid rgba(15,110,180,0.45);
        font-weight: 700;
    }
    
    /* -------- Buttons -------- */
    QPushButton {
        border: 1px solid rgba(10,40,70,0.22);
        background: rgba(255,255,255,0.78);
        padding: 6px 10px;
        border-radius: 10px;
    }
    QPushButton:hover { background: rgba(255,255,255,0.92); }
    QPushButton:pressed { background: rgba(210,235,255,0.95); }
    QPushButton:focus { outline: none; border: 1px solid rgba(10,40,70,0.22); } /* remove inner focus artifact */

    QPushButton#bigSquare {
        font-size: 16pt;
        font-weight: 700;
        border-radius: 18px;
        padding: 16px;
        background: rgba(255,255,255,0.72);
    }
    QPushButton#bigSquare:hover { background: rgba(255,255,255,0.90); }
    QPushButton#bigSquare:pressed { background: rgba(210,235,255,0.95); }

    /* -------- Lists -------- */
    QListWidget#listClean {
        background: rgba(255,255,255,0.70);
        border: 1px solid rgba(10,40,70,0.18);
        border-radius: 10px;
        padding: 6px;
    }
    QListWidget#listClean::item {
        padding: 8px 10px;
        border-radius: 8px;
    }
    QListWidget#listClean::item:selected {
        background: rgba(210,235,255,0.95);
        color: #0b1b2b;
    }

    /* Word context display */
    QLabel#contextLine {
        border: 1px solid rgba(10,40,70,0.18);
        border-radius: 10px;
        padding: 6px 10px;
        background: rgba(255,255,255,0.70);
    }
    .activeWord {
        font-weight: 800;
        padding: 2px 6px;
        border-radius: 8px;
        background: rgba(210,235,255,0.95);
        border: 1px solid rgba(10,40,70,0.18);
    }
    .ctxWord {
        opacity: 0.85;
    }

"""
