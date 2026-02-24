from __future__ import annotations

from pathlib import Path
from typing import Optional, List, Dict, Any

from PySide6 import QtWidgets, QtCore, QtGui

from ..widgets import Card, TopBar
from ..store import DataStore, Project
from ..daf_engine import ensure_page_layout, PageLayout
from ..models.selection import Selection
from .create_shared import Cursor, clamp_cursor, extract_words_in_range


class ExplanationDelegate(QtWidgets.QStyledItemDelegate):
    """Inline explanation editor with automatic dropdown suggestions."""

    def __init__(self, ds: DataStore, parent=None):
        super().__init__(parent)
        self.ds = ds

    def createEditor(self, parent, option, index):
        editor = QtWidgets.QLineEdit(parent)
        editor.setObjectName("cellEditor")
        editor.setClearButtonEnabled(True)
        editor.setStyleSheet(
            "QLineEdit#cellEditor{padding:6px 12px; min-height:28px; border:1px solid #cbd5e1; border-radius:16px;}"
        )

        # Build suggestions based on word in same row
        try:
            table = parent
            row = index.row()
            word_idx = index.sibling(row, 0)
            word = (word_idx.data() or "").strip()
        except Exception:
            word = ""

        suggestions = self.ds.suggest_explanations(word, limit=80) if word else []
        # completer shows display strings, but we insert the english/hebrew value.
        model = QtGui.QStandardItemModel()
        for display, eng, heb in suggestions:
            item = QtGui.QStandardItem(display)
            item.setData(eng, QtCore.Qt.UserRole + 1)
            item.setData(heb, QtCore.Qt.UserRole + 2)
            model.appendRow(item)

        completer = QtWidgets.QCompleter(model, editor)
        completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        completer.setFilterMode(QtCore.Qt.MatchContains)
        completer.setCompletionMode(QtWidgets.QCompleter.PopupCompletion)
        editor.setCompleter(completer)

        def on_activated(text: str):
            # Find selected item in completer popup, write english if exists else hebrew.
            idx = completer.currentIndex()
            eng = idx.data(QtCore.Qt.UserRole + 1) or ""
            heb = idx.data(QtCore.Qt.UserRole + 2) or ""
            editor.setText((eng or heb or text or "").strip())

        completer.activated.connect(on_activated)

        # Show popup immediately after focus
        QtCore.QTimer.singleShot(0, lambda: completer.complete())
        return editor


class CreateEditorPage(QtWidgets.QWidget):
    """Page 2/2: full-screen editor table + Save + Back to Picker."""

    back_to_picker = QtCore.Signal()
    home = QtCore.Signal()
    saved = QtCore.Signal()
    exportRequested = QtCore.Signal(str)  # project_id

    def __init__(self, ds: DataStore, project_root: Path, parent=None):
        super().__init__(parent)
        self.ds = ds
        self.project_root = project_root

        self._project: Optional[Project] = None
        self._selection: Optional[Selection] = None
        self._layout: Optional[PageLayout] = None
        self._layout_error: Optional[str] = None

        self._dirty: bool = False
        self._suppress_dirty: bool = False

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(12)

        self.top = TopBar("Create — Editor", show_back=True, show_home=False)
        self.top.back_clicked.connect(self.back_to_picker.emit)
        outer.addWidget(self.top)

        # Header row: page label + save/export buttons
        hdr = QtWidgets.QHBoxLayout()
        hdr.setSpacing(10)

        self.lbl_title = QtWidgets.QLabel("—")
        self.lbl_title.setObjectName("h2")

        self.btn_save = QtWidgets.QPushButton("Save")
        self.btn_save.setFixedHeight(36)
        self.btn_save.setCursor(QtCore.Qt.PointingHandCursor)

        self.btn_export = QtWidgets.QPushButton("Export")
        self.btn_export.setFixedHeight(36)
        self.btn_export.setCursor(QtCore.Qt.PointingHandCursor)

        self.lbl_saved = QtWidgets.QLabel("Saved")
        self.lbl_saved.setObjectName("muted")

        self.lbl_meta = QtWidgets.QLabel("—")
        self.lbl_meta.setObjectName("muted")

        hdr.addWidget(self.lbl_title)
        hdr.addStretch(1)
        hdr.addWidget(self.lbl_saved)
        hdr.addWidget(self.btn_export)
        hdr.addWidget(self.btn_save)
        outer.addLayout(hdr)
        outer.addWidget(self.lbl_meta)

        # Table
        self.table_card = Card()
        tlay = QtWidgets.QVBoxLayout(self.table_card)
        tlay.setContentsMargins(0, 0, 0, 0)

        self.table = QtWidgets.QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Word", "Explanation"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        # Editing should feel like: click into Explanation -> cursor + dropdown.
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.SelectedClicked | QtWidgets.QAbstractItemView.EditKeyPressed)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(True)
        self.table.setObjectName("mainTable")
        self.table.setColumnWidth(0, 260)

        tlay.addWidget(self.table)
        outer.addWidget(self.table_card, 1)

        self.btn_save.clicked.connect(self._on_save)
        self.btn_export.clicked.connect(self._on_export)

        # Mark dirty whenever user edits anything
        self.table.itemChanged.connect(self._on_item_changed)
        # Click explanation cell -> immediately edit (shows dropdown)
        self.table.cellClicked.connect(self._on_cell_clicked)

        # Delegate for Explanation column (inline dropdown + padding)
        self.table.setItemDelegateForColumn(1, ExplanationDelegate(self.ds, self.table))

        # Merge rows
        self.table.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._table_context_menu)

    # ----- public API

    def set_project(self, pr: Project) -> None:
        self._project = pr
        self._reload_table_from_project()
        self._refresh_header()

    def load_selection(self, sel: Selection) -> None:
        self._selection = sel
        self._load_layout_for_selection()
        self._refresh_header()

        # Only auto-generate if project has no rows (avoid nuking edits).
        if self._project and (not self._project.rows):
            self._generate_rows_from_selection()

    # ----- internals

    def _refresh_header(self) -> None:
        # Title should be the actual daf/amud range, not the internal working-page title.
        if self._selection:
            rng = f"{self._selection.masechta} {self._selection.start_daf}{self._selection.start_amud} → {self._selection.end_daf}{self._selection.end_amud}"
            self.lbl_title.setText(rng)
            self.lbl_meta.setText(f"Table rows: {self.table.rowCount()}")
        else:
            # Fallback: project metadata
            if self._project:
                self.lbl_title.setText(f"{self._project.masechta} {self._project.daf}")
            else:
                self.lbl_title.setText("Editor")
            self.lbl_meta.setText(f"Table rows: {self.table.rowCount()}")

        self._refresh_saved_badge()

    def _refresh_saved_badge(self) -> None:
        self.lbl_saved.setText("Not saved" if self._dirty else "Saved")

    def _set_dirty(self, dirty: bool) -> None:
        self._dirty = dirty
        self._refresh_saved_badge()

    def _on_item_changed(self, *_args) -> None:
        if self._suppress_dirty:
            return
        if not self._dirty:
            self._set_dirty(True)

    def is_dirty(self) -> bool:
        return bool(self._dirty)

    def save_now(self) -> None:
        self._on_save()

    def _load_layout_for_selection(self) -> None:
        if not self._selection:
            self._layout = None
            self._layout_error = None
            return
        # Kept for backward compatibility. For multi-page ranges we load pages on demand.
        layout, err = ensure_page_layout(
            self.project_root,
            masechta=self._selection.masechta,
            daf=self._selection.start_daf,
            amud=self._selection.start_amud,
        )
        self._layout = layout
        self._layout_error = err

    def _generate_rows_from_selection(self) -> None:
        if not self._project or not self._selection:
            return
        if self._layout_error:
            self.lbl_meta.setText(self._layout_error)
            return
        if not self._layout:
            self.lbl_meta.setText("No layout loaded.")
            return

        words = self._extract_words_for_selection(self._selection)

        # Replace table with fresh rows (since project was empty)
        self._suppress_dirty = True
        self.table.setRowCount(0)
        for w in words:
            r = self.table.rowCount()
            self.table.insertRow(r)
            itw = QtWidgets.QTableWidgetItem(w)
            itw.setFlags(itw.flags() & ~QtCore.Qt.ItemIsEditable)
            self.table.setItem(r, 0, itw)
            self.table.setItem(r, 1, QtWidgets.QTableWidgetItem(""))
        self._suppress_dirty = False

        # Update project metadata to match selection
        self._project.masechta = self._selection.masechta
        self._project.perek = self._selection.perek
        self._project.daf = f"{self._selection.start_daf}{self._selection.start_amud}"
        self._sync_project_from_table()

        self._set_dirty(False)

        self._refresh_header()

    def _reload_table_from_project(self) -> None:
        self._suppress_dirty = True
        self.table.setRowCount(0)
        if not self._project:
            self._suppress_dirty = False
            return
        rows = self._project.rows or []
        for row in rows:
            r = self.table.rowCount()
            self.table.insertRow(r)
            itw = QtWidgets.QTableWidgetItem(row.get("word", ""))
            itw.setFlags(itw.flags() & ~QtCore.Qt.ItemIsEditable)
            self.table.setItem(r, 0, itw)
            self.table.setItem(r, 1, QtWidgets.QTableWidgetItem(row.get("explanation", "")))
        self._suppress_dirty = False
        self._set_dirty(False)

    def _sync_project_from_table(self) -> None:
        if not self._project:
            return
        rows: List[Dict[str, Any]] = []
        for r in range(self.table.rowCount()):
            w = self.table.item(r, 0).text() if self.table.item(r, 0) else ""
            e = self.table.item(r, 1).text() if self.table.item(r, 1) else ""
            rows.append({"word": w, "explanation": e})
        self._project.rows = rows
        self.ds.update_project(self._project)

    def _on_save(self) -> None:
        if not self._project:
            return

        # Name dialog only on first save if not named yet
        meta = self._project.meta or {}
        named = bool(meta.get("named"))
        if not named:
            default_base = ""
            if self._selection:
                default_base = f"{self._selection.masechta} {self._selection.start_daf}{self._selection.start_amud}"
            if not default_base:
                default_base = (self._project.title or "").strip()
            if not default_base:
                default_base = "Untitled"

            suggested = self.ds.make_unique_project_title(default_base, exclude_id=self._project.id)
            title, ok = QtWidgets.QInputDialog.getText(
                self,
                "Save Working Page",
                "Name this working page (it will appear in Browse):",
                text=suggested,
            )
            if not ok:
                return
            title = (title or "").strip() or suggested
            title = self.ds.make_unique_project_title(title, exclude_id=self._project.id)
            self._project.title = title
            meta["named"] = True
            self._project.meta = meta
        self._sync_project_from_table()

        # Also merge any filled explanations into the global words store.
        # Dedup rule: same (norm + english) => one entry, append new source.
        source = ""
        if self._selection:
            source = f"{self._selection.masechta} {self._selection.start_daf}{self._selection.start_amud}"
        for r in range(self.table.rowCount()):
            w_item = self.table.item(r, 0)
            e_item = self.table.item(r, 1)
            if not w_item or not e_item:
                continue
            word = (w_item.text() or "").strip()
            expl = (e_item.text() or "").strip()
            if not word or not expl:
                continue
            # word_nikud: keep same as raw for now
            self.ds.upsert_word(word_raw=word, word_nikud=word, english=expl, hebrew="", source=source)

        self.ds.save_all()

        self.saved.emit()
        self._set_dirty(False)
        self._refresh_header()

    def _on_cell_clicked(self, row: int, col: int) -> None:
        # Clicking explanation cell should immediately enter edit mode (shows dropdown)
        if col != 1:
            return
        it = self.table.item(row, col)
        if it is None:
            it = QtWidgets.QTableWidgetItem("")
            self.table.setItem(row, col, it)
        self.table.editItem(it)

    def _table_context_menu(self, pos) -> None:
        sel = self.table.selectionModel().selectedRows()
        if not sel or len(sel) < 2:
            return
        rows = sorted({i.row() for i in sel})
        if len(rows) < 2:
            return
        menu = QtWidgets.QMenu(self)
        act_merge = menu.addAction(f"Merge {len(rows)} rows")
        chosen = menu.exec(self.table.mapToGlobal(pos))
        if chosen == act_merge:
            self._merge_rows(rows)

    def _merge_rows(self, rows: List[int]) -> None:
        if not self._project or not rows:
            return
        rows = sorted(rows)
        base = rows[0]
        words = []
        expl = ""
        for r in rows:
            w = self.table.item(r, 0).text() if self.table.item(r, 0) else ""
            e = self.table.item(r, 1).text() if self.table.item(r, 1) else ""
            if w:
                words.append(w.strip())
            if not expl and e.strip():
                expl = e.strip()

        merged_word = " ".join([w for w in words if w])
        self._suppress_dirty = True
        self.table.item(base, 0).setText(merged_word)
        self.table.item(base, 1).setText(expl)
        # remove from bottom up
        for r in reversed(rows[1:]):
            self.table.removeRow(r)
        self._suppress_dirty = False
        self._set_dirty(True)

    def _ensure_named(self) -> bool:
        if not self._project:
            return False
        meta = self._project.meta or {}
        if meta.get("named"):
            return True
        # trigger name dialog via save flow but without actually requiring edits
        was_dirty = self._dirty
        self._dirty = True
        self._on_save()
        return bool((self._project.meta or {}).get("named"))

    def _on_export(self) -> None:
        # Export should auto-save if needed
        if not self._project:
            return
        if self._dirty:
            # will prompt for name only if unnamed
            self._on_save()
        else:
            # if not dirty but unnamed, still name it before export
            if not self._ensure_named():
                return

        self.exportRequested.emit(self._project.id)

    def _extract_words_for_selection(self, sel: Selection) -> List[str]:
        """Extract words across pages (inclusive range)."""
        masechta = sel.masechta

        def page_index(daf: int, amud: str) -> int:
            return daf * 2 + (0 if amud == "a" else 1)

        start_i = page_index(sel.start_daf, sel.start_amud)
        end_i = page_index(sel.end_daf, sel.end_amud)
        if end_i < start_i:
            start_i, end_i = end_i, start_i

        words: List[str] = []
        for pi in range(start_i, end_i + 1):
            daf = pi // 2
            amud = "a" if (pi % 2) == 0 else "b"
            layout, err = ensure_page_layout(self.project_root, masechta=masechta, daf=daf, amud=amud)
            if err or not layout:
                continue
            if pi == start_i:
                start = clamp_cursor(layout, Cursor(sel.start_line_i, sel.start_word_i))
            else:
                start = Cursor(0, 0)
            if pi == end_i:
                end = clamp_cursor(layout, Cursor(sel.end_line_i, sel.end_word_i))
            else:
                # end of page
                from .create_shared import last_cursor
                end = last_cursor(layout)
            words.extend(extract_words_in_range(layout, start, end))
        return [w for w in words if (w or "").strip()]
