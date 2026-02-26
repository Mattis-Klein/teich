from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6 import QtCore, QtGui, QtWidgets

from ..daf_engine import PageLayout, ensure_page_layout
from ..models.selection import Selection
from ..store import DataStore, Project
from ..widgets import Card, TopBar
from .create_shared import Cursor, clamp_cursor,  extract_words_in_range, first_cursor, last_cursor


class ExplanationDelegate(QtWidgets.QStyledItemDelegate):
    """Multiline explanation editor:
    - row grows cleanly to fit text
    - right-click shows Teich menu (Undo/Redo/Cut/Copy/Paste/Clear + Suggestions)
    - suggestions appear when user double-clicks/clicks into the cell (via CreateEditorPage)
    """

    def __init__(self, ds: DataStore, table: QtWidgets.QTableWidget, parent=None):
        super().__init__(parent)
        self.ds = ds
        self.table = table

    def createEditor(self, parent, option, index):
        editor = QtWidgets.QTextEdit(parent)
        editor.setObjectName("cellEditor")
        editor.setAcceptRichText(False)
        editor.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        editor.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        editor.setWordWrapMode(QtGui.QTextOption.WrapAtWordBoundaryOrAnywhere)
        editor.setStyleSheet(
            "QTextEdit#cellEditor{padding:6px 12px; border:1px solid #cbd5e1; border-radius:16px;}"
        )

        editor.setProperty("_teich_row", index.row())

        # Auto-grow row as text changes
        editor.textChanged.connect(lambda: self._auto_resize_row(editor))

        # Replace default context menu with Teich menu
        editor.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        editor.customContextMenuRequested.connect(lambda p: self._show_teich_menu(editor, p))

        # Pop suggestions immediately (like old behavior), but as a Teich popup
        QtCore.QTimer.singleShot(0, lambda: self._show_suggestions_popup(editor))

        return editor

    def setEditorData(self, editor, index):
        if isinstance(editor, QtWidgets.QTextEdit):
            editor.blockSignals(True)
            editor.setPlainText(index.data() or "")
            editor.blockSignals(False)
            self._auto_resize_row(editor)
            return
        super().setEditorData(editor, index)

    def setModelData(self, editor, model, index):
        if isinstance(editor, QtWidgets.QTextEdit):
            model.setData(index, editor.toPlainText().strip())
            return
        super().setModelData(editor, model, index)

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)

    def _auto_resize_row(self, editor: QtWidgets.QTextEdit) -> None:
        row = int(editor.property("_teich_row") or -1)
        if row < 0:
            return
        doc_h = int(editor.document().size().height())
        target = max(34, doc_h + 16)
        self.table.setRowHeight(row, target)

    def _word_for_row(self, row: int) -> str:
        it = self.table.item(row, 0)
        return (it.text() if it else "").strip()

    def _show_suggestions_popup(self, editor: QtWidgets.QTextEdit) -> None:
        row = int(editor.property("_teich_row") or -1)
        if row < 0:
            return
        word = self._word_for_row(row)
        if not word:
            return
        suggestions = self.ds.suggest_explanations(word, limit=40) or []
        if not suggestions:
            return

        menu = QtWidgets.QMenu(editor)
        # Show ONLY the explanation text (no sources in the list)
        for display, eng, heb in suggestions[:15]:
            label = (eng or "").strip() or (heb or "").strip()
            if not label:
                # fallback: strip possible "— sources" suffix
                label = (display or "").split("—", 1)[0].strip()
            act = menu.addAction(label)
            act.setData((eng or "", heb or "", label))

        gpos = editor.mapToGlobal(QtCore.QPoint(10, editor.height()))
        chosen = menu.exec(gpos)
        if not chosen:
            return
        eng, heb, disp = chosen.data()
        editor.setPlainText((eng or heb or disp or "").strip())
        self._auto_resize_row(editor)

    def _show_teich_menu(self, editor: QtWidgets.QTextEdit, pos: QtCore.QPoint) -> None:
        row = int(editor.property("_teich_row") or -1)
        word = self._word_for_row(row) if row >= 0 else ""

        menu = QtWidgets.QMenu(editor)

        act_undo = menu.addAction("Undo")
        act_redo = menu.addAction("Redo")
        menu.addSeparator()
        act_cut = menu.addAction("Cut")
        act_copy = menu.addAction("Copy")
        act_paste = menu.addAction("Paste")
        menu.addSeparator()
        act_clear = menu.addAction("Clear")

        sugg_menu = menu.addMenu("Suggestions")
        suggestions = self.ds.suggest_explanations(word, limit=30) if word else []
        if suggestions:
            for display, eng, heb in suggestions[:15]:
                label = (eng or "").strip() or (heb or "").strip()
                if not label:
                    label = (display or "").split("—", 1)[0].strip()
                a = sugg_menu.addAction(label)
                a.setData((eng or "", heb or "", label))
        else:
            a = sugg_menu.addAction("(none)")
            a.setEnabled(False)

        chosen = menu.exec(editor.mapToGlobal(pos))
        if not chosen:
            return

        if chosen == act_undo:
            editor.undo()
        elif chosen == act_redo:
            editor.redo()
        elif chosen == act_cut:
            editor.cut()
        elif chosen == act_copy:
            editor.copy()
        elif chosen == act_paste:
            editor.paste()
        elif chosen == act_clear:
            editor.setPlainText("")
        else:
            data = chosen.data()
            if isinstance(data, tuple) and len(data) == 3:
                eng, heb, disp = data
                editor.setPlainText((eng or heb or disp or "").strip())

        self._auto_resize_row(editor)


class CreateEditorPage(QtWidgets.QWidget):
    """Page 2/2: full-screen editor table + Save + Back to Picker."""

    back_to_picker = QtCore.Signal()
    home = QtCore.Signal()
    saved = QtCore.Signal()
    exportRequested = QtCore.Signal(str)  # project_id

    def __init__(self, ds: DataStore, project_root: Path, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
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

        # Header row: title + save/export
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

        self.table.setEditTriggers(
            QtWidgets.QAbstractItemView.SelectedClicked | QtWidgets.QAbstractItemView.EditKeyPressed
        )
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(True)
        self.table.setObjectName("mainTable")
        self.table.setColumnWidth(0, 260)

        tlay.addWidget(self.table)
        outer.addWidget(self.table_card, 1)

        # Delegate for Explanation column
        self.table.setItemDelegateForColumn(1, ExplanationDelegate(self.ds, self.table, self.table))

        # Signals
        self.btn_save.clicked.connect(self._on_save)
        self.btn_export.clicked.connect(self._on_export)

        self.table.itemChanged.connect(self._on_item_changed)
        self.table.cellClicked.connect(self._on_cell_clicked)

        # Merge rows context menu (existing behavior)
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

        # Only auto-generate if project has no rows
        if self._project and (not self._project.rows):
            self._generate_rows_from_selection()

    # ----- internals
    def _refresh_header(self) -> None:
        if self._selection:
            rng = f"{self._selection.masechta} {self._selection.start_daf}{self._selection.start_amud} → {self._selection.end_daf}{self._selection.end_amud}"
            self.lbl_title.setText(rng)
        elif self._project:
            self.lbl_title.setText(f"{self._project.masechta} {self._project.daf}")
        else:
            self.lbl_title.setText("Editor")

        # Hide noisy row count (not useful in production UX)
        self.lbl_meta.setText("")
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

        # Back-compat: for multi-page ranges load first page; word extraction loads on demand.
        layout, err = ensure_page_layout(
            self.project_root,
            masechta=self._selection.masechta,
            daf=self._selection.start_daf,
            amud=self._selection.start_amud,
        )
        self._layout = layout
        self._layout_error = err

    def _reload_table_from_project(self) -> None:
        self._suppress_dirty = True
        try:
            self.table.setRowCount(0)
            if not self._project:
                return
            for r in (self._project.rows or []):
                self._append_row(word=r.get("word", ""), explanation=r.get("explanation", ""))
        finally:
            self._suppress_dirty = False
            self._set_dirty(False)

    def _append_row(self, word: str, explanation: str) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)

        it_word = QtWidgets.QTableWidgetItem(word)
        it_word.setFlags(it_word.flags() & ~QtCore.Qt.ItemIsEditable)  # word column locked
        self.table.setItem(row, 0, it_word)

        it_expl = QtWidgets.QTableWidgetItem(explanation or "")
        self.table.setItem(row, 1, it_expl)

        # Make sure row height isn't tiny
        self.table.setRowHeight(row, 34)

    def _generate_rows_from_selection(self) -> None:
        if not (self._project and self._selection):
            return

        sel = self._selection

        def _amud_idx(a: str) -> int:
            return 0 if (a or "").lower() == "a" else 1

        def _iter_pages_in_range():
            # deterministic order: daf ascending, then amud a->b
            for daf in range(int(sel.start_daf), int(sel.end_daf) + 1):
                amuds = ["a", "b"]
                if daf == int(sel.start_daf) and daf == int(sel.end_daf):
                    # same daf: from start_amud to end_amud
                    a0 = _amud_idx(sel.start_amud)
                    a1 = _amud_idx(sel.end_amud)
                    for a in amuds[a0 : a1 + 1]:
                        yield daf, a
                elif daf == int(sel.start_daf):
                    a0 = _amud_idx(sel.start_amud)
                    for a in amuds[a0:]:
                        yield daf, a
                elif daf == int(sel.end_daf):
                    a1 = _amud_idx(sel.end_amud)
                    for a in amuds[: a1 + 1]:
                        yield daf, a
                else:
                    for a in amuds:
                        yield daf, a

        words: List[str] = []

        pages = list(_iter_pages_in_range())
        if not pages:
            return

        for i, (daf, amud) in enumerate(pages):
            layout, err = ensure_page_layout(
                self.project_root,
                masechta=sel.masechta,
                daf=daf,
                amud=amud,
            )
            if err or not layout:
                # Fail loudly but continue collecting other pages
                QtWidgets.QMessageBox.warning(
                    self,
                    "Layout missing",
                    f"Could not load layout for {sel.masechta} {daf}{amud}.\n\n{err or ''}".strip(),
                )
                continue

            # Compute page-local start/end cursor
            if i == 0:
                start = Cursor(sel.start_line_i, sel.start_word_i)
            else:
                start = first_cursor(layout)

            if i == len(pages) - 1:
                end = Cursor(sel.end_line_i, sel.end_word_i)
            else:
                end = last_cursor(layout)

            words.extend(extract_words_in_range(layout, start, end))

        # Build table
        self._suppress_dirty = True
        try:
            self.table.setRowCount(0)
            for w in words:
                self._append_row(word=w, explanation="")
        finally:
            self._suppress_dirty = False

        self._set_dirty(True)  # generated content is unsaved
        self._sync_table_to_project()

    def _sync_table_to_project(self) -> None:
        if not self._project:
            return
        rows = []
        for r in range(self.table.rowCount()):
            word = (self.table.item(r, 0).text() if self.table.item(r, 0) else "").strip()
            expl = (self.table.item(r, 1).text() if self.table.item(r, 1) else "").strip()
            rows.append({"word": word, "explanation": expl})
        self._project.rows = rows
        self.ds.update_project(self._project)

    def _on_cell_clicked(self, r: int, c: int) -> None:
        # Click Explanation cell -> immediately edit (so suggestions show)
        if c == 1:
            self.table.editItem(self.table.item(r, c))

    def _on_save(self) -> None:
        if not self._project:
            return

        # If not named yet (or still Untitled), force naming on save
        named = bool((self._project.meta or {}).get("named"))
        is_untitled = (self._project.title or "").strip().lower() in ("", "untitled")

        if (not named) or is_untitled:
            title, ok = QtWidgets.QInputDialog.getText(
                self,
                "Save project",
                "Project name:",
                text=(self._project.title or "").strip() if not is_untitled else "",
            )
            if not ok:
                return
            title = (title or "").strip()
            if not title:
                QtWidgets.QMessageBox.warning(self, "Invalid name", "Project name cannot be empty.")
                return
            title = self.ds.make_unique_project_title(title, exclude_id=self._project.id)
            self._project.title = title
            self._project.meta = self._project.meta or {}
            self._project.meta["named"] = True
            self.ds.update_project(self._project)

        self._sync_table_to_project()
        self.ds.save_all()
        self._set_dirty(False)
        self.saved.emit()

    def _on_export(self) -> None:
        if not self._project:
            return
        if self._dirty:
            # autosave before export (your design)
            self._on_save()
        self.exportRequested.emit(self._project.id)

    def _table_context_menu(self, pos) -> None:
        menu = QtWidgets.QMenu(self)
        act_merge = menu.addAction("Merge selected rows")
        act_sources = menu.addAction("Sources for selected word")

        chosen = menu.exec(self.table.mapToGlobal(pos))
        if not chosen:
            return

        if chosen == act_sources:
            r = self.table.currentRow()
            if r < 0:
                return
            word = (self.table.item(r, 0).text() if self.table.item(r, 0) else "").strip()
            if not word:
                return
            hits = self.ds.search_words(word, limit=200)
            srcs: list[str] = []
            for h in hits:
                for s in (getattr(h, "sources", []) or []):
                    if s not in srcs:
                        srcs.append(s)
            msg = "\n".join(f"• {s}" for s in srcs) if srcs else "(no sources)"
            QtWidgets.QMessageBox.information(self, "Sources", msg)
            return

        if chosen != act_merge:
            return

        rows = sorted({idx.row() for idx in self.table.selectedIndexes()})
        if len(rows) < 2:
            return

        btn = QtWidgets.QMessageBox.question(
            self,
            "Merge",
            "Merge the selected rows into ONE new combined word?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        if btn != QtWidgets.QMessageBox.Yes:
            return

        base = rows[0]
        words = []
        merged_expl: list[str] = []
        for r in rows:
            wtxt = (self.table.item(r, 0).text() if self.table.item(r, 0) else "").strip()
            if wtxt:
                words.append(wtxt)
            etxt = (self.table.item(r, 1).text() if self.table.item(r, 1) else "").strip()
            if etxt:
                merged_expl.append(etxt)

        merged_word = " ".join(words).strip()
        merged_expl_txt = "\n".join(dict.fromkeys(merged_expl))

        # Create a NEW WordEntry for this merged token/phrase (deterministic via UUID5)
        if merged_word:
            self.ds.upsert_word(
                word_raw=merged_word,
                word_nikud="",
                english="",
                hebrew="",
                source="merge",
            )

        # Replace base row with merged content
        if self.table.item(base, 0):
            self.table.item(base, 0).setText(merged_word)
        if self.table.item(base, 1):
            self.table.item(base, 1).setText(merged_expl_txt)

        # Remove other rows
        for r in reversed(rows[1:]):
            self.table.removeRow(r)

        self._set_dirty(True)
        self._sync_table_to_project()
