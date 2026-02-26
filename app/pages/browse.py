from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from PySide6 import QtCore, QtGui, QtWidgets

from ..store import DataStore
from ..widgets import Card, TopBar 


class BrowsePage(QtWidgets.QWidget):
    """Browse page.

    Modes:
    - files: 3 columns (Working Pages, Exported, Imported)
    - words: table (English, Hebrew, Word-with-nikud)
    """

    open_project = QtCore.Signal(str)
    go_home = QtCore.Signal()

    def __init__(self, ds: DataStore, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.ds = ds
        self.mode = "files"  # files | words

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(12)

        self.top = TopBar("Browse", show_back=True, show_home=False)
        self.top.back_clicked.connect(self.go_home.emit)
        self.top.home_clicked.connect(self.go_home.emit)
        outer.addWidget(self.top)

        # Search row
        search_row = QtWidgets.QHBoxLayout()
        search_row.setSpacing(10)

        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("Search…")
        self.search.setFixedHeight(34)

        self.btn_files = QtWidgets.QPushButton("Files")
        self.btn_words = QtWidgets.QPushButton("Words")
        for b in (self.btn_files, self.btn_words):
            b.setFixedHeight(34)
            b.setCheckable(True)
        self.btn_files.setChecked(True)

        search_row.addWidget(self.search, 1)
        search_row.addWidget(self.btn_files)
        search_row.addWidget(self.btn_words)
        outer.addLayout(search_row)

        # Content
        self.card = Card()
        content = QtWidgets.QVBoxLayout(self.card)
        content.setContentsMargins(14, 14, 14, 14)
        content.setSpacing(12)

        # -------- Files view
        self.files_widget = QtWidgets.QWidget()
        fw = QtWidgets.QHBoxLayout(self.files_widget)
        fw.setContentsMargins(0, 0, 0, 0)
        fw.setSpacing(12)

        def mk_group(title: str) -> tuple[QtWidgets.QGroupBox, QtWidgets.QListWidget]:
            g = QtWidgets.QGroupBox(title)
            lay = QtWidgets.QVBoxLayout(g)
            lay.setContentsMargins(10, 10, 10, 10)
            lst = QtWidgets.QListWidget()
            lst.setObjectName("listClean")
            lst.setFrameShape(QtWidgets.QFrame.NoFrame)
            lst.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
            lay.addWidget(lst)
            return g, lst

        # Order: Working / Exported / Imported
        self.grp_working, self.lst_working = mk_group("Working Pages")
        self.grp_exported, self.lst_exported = mk_group("Exported")
        self.grp_imported, self.lst_imported = mk_group("Imported")

        fw.addWidget(self.grp_working, 1)
        fw.addWidget(self.grp_exported, 1)
        fw.addWidget(self.grp_imported, 1)

        # Right-click menus
        self.lst_working.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.lst_working.customContextMenuRequested.connect(self._working_context_menu)
        self.lst_exported.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.lst_exported.customContextMenuRequested.connect(self._exported_context_menu)
        self.lst_imported.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.lst_imported.customContextMenuRequested.connect(self._imported_context_menu)

        self.lst_working.itemDoubleClicked.connect(self._open_selected_working)
        self.lst_exported.itemDoubleClicked.connect(self._open_selected_export)

        # -------- Words view
        self.words_widget = QtWidgets.QWidget()
        ww = QtWidgets.QVBoxLayout(self.words_widget)
        ww.setContentsMargins(0, 0, 0, 0)
        ww.setSpacing(10)

        # Sort controls (Words mode only)
        sort_row = QtWidgets.QHBoxLayout()
        sort_row.setSpacing(8)
        sort_row.addStretch(1)

        self.cbo_sort_by = QtWidgets.QComboBox()
        self.cbo_sort_by.addItems(["Word", "Hebrew", "English"])
        self.cbo_sort_by.setFixedHeight(30)

        self.cbo_sort_order = QtWidgets.QComboBox()
        self.cbo_sort_order.addItems(["Asc", "Desc"])
        self.cbo_sort_order.setFixedHeight(30)

        sort_row.addWidget(QtWidgets.QLabel("Sort:"))
        sort_row.addWidget(self.cbo_sort_by)
        sort_row.addWidget(self.cbo_sort_order)
        ww.addLayout(sort_row)

        # Words table: 3 columns, with Word on the RIGHT
        # (Qt tables are LTR; ordering columns as [English, Hebrew, Word] matches your request.)
        self.tbl_words = QtWidgets.QTableWidget(0, 3)
        self.tbl_words.setHorizontalHeaderLabels(["English", "Hebrew", "Word"])
        self.tbl_words.horizontalHeader().setStretchLastSection(False)
        self.tbl_words.verticalHeader().setVisible(False)
        self.tbl_words.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.tbl_words.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.tbl_words.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.tbl_words.setAlternatingRowColors(True)
        self.tbl_words.setObjectName("mainTable")

        # Widths: Word ~20%, Hebrew/English share the rest
        self.tbl_words.setColumnWidth(2, 260)  # Word (right)
        self.tbl_words.setColumnWidth(1, 520)  # Hebrew
        self.tbl_words.setColumnWidth(0, 520)  # English
        ww.addWidget(self.tbl_words, 1)

        # Words context menu
        self.tbl_words.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.tbl_words.customContextMenuRequested.connect(self._words_context_menu)

        content.addWidget(self.files_widget)
        content.addWidget(self.words_widget)
        outer.addWidget(self.card, 1)

        # Wire signals
        self.btn_files.clicked.connect(lambda: self._set_mode("files"))
        self.btn_words.clicked.connect(lambda: self._set_mode("words"))
        self.search.textChanged.connect(lambda _t: self.refresh())
        self.cbo_sort_by.currentIndexChanged.connect(lambda _i: self.refresh())
        self.cbo_sort_order.currentIndexChanged.connect(lambda _i: self.refresh())

        self.refresh()
        self._apply_mode()

    # ----------------- mode / refresh -----------------
    def _set_mode(self, mode: str) -> None:
        self.mode = mode
        self.btn_files.setChecked(mode == "files")
        self.btn_words.setChecked(mode == "words")
        self._apply_mode()
        self.refresh()

    def _apply_mode(self) -> None:
        self.files_widget.setVisible(self.mode == "files")
        self.words_widget.setVisible(self.mode == "words")

    def refresh(self) -> None:
        q = (self.search.text() or "").strip()
        if self.mode == "words":
            self._refresh_words(q)
        else:
            self._refresh_files(q)

    # ----------------- files mode -----------------
    def _refresh_files(self, q: str) -> None:
        self.lst_imported.clear()
        self.lst_working.clear()
        self.lst_exported.clear()

        all_files = self.ds.list_files()
        projects = self.ds.list_projects()

        def match_title(title: str) -> bool:
            if not q:
                return True
            return q.casefold() in (title or "").casefold()

        def match_project(pr) -> bool:
            if not q:
                return True
            qq = q.casefold()
            if qq in (pr.title or "").casefold():
                return True
            for r in (pr.rows or []):
                if qq in (r.get("word", "") or "").casefold() or qq in (r.get("explanation", "") or "").casefold():
                    return True
            return False

        # Working
        for pr in projects:
            if bool((pr.meta or {}).get("closed")):
                continue
            if not match_project(pr):
                continue
            it = QtWidgets.QListWidgetItem(pr.title)
            it.setData(QtCore.Qt.UserRole, pr.id)
            self.lst_working.addItem(it)
            self._style_file_item(it, q)

        # Exported
        for f in all_files:
            if f.get("kind") != "export":
                continue
            title = f.get("title", "")
            if not match_title(title):
                continue
            fmt = f.get("format", "")
            label = f"{title} ({fmt})" if fmt else title
            it = QtWidgets.QListWidgetItem(label)
            it.setData(QtCore.Qt.UserRole, f)
            self.lst_exported.addItem(it)
            self._style_file_item(it, q)

        # Imported
        for f in all_files:
            if f.get("kind") != "import":
                continue
            title = f.get("title", "")
            if not match_title(title):
                continue
            it = QtWidgets.QListWidgetItem(title)
            it.setData(QtCore.Qt.UserRole, f)
            self.lst_imported.addItem(it)
            self._style_file_item(it, q)

        if self.lst_working.count() == 0:
            it = QtWidgets.QListWidgetItem("No working pages yet.")
            it.setFlags(QtCore.Qt.NoItemFlags)
            self.lst_working.addItem(it)
        if self.lst_exported.count() == 0:
            it = QtWidgets.QListWidgetItem("No exported files yet.")
            it.setFlags(QtCore.Qt.NoItemFlags)
            self.lst_exported.addItem(it)
        if self.lst_imported.count() == 0:
            it = QtWidgets.QListWidgetItem("No imported items yet.")
            it.setFlags(QtCore.Qt.NoItemFlags)
            self.lst_imported.addItem(it)

    def _style_file_item(self, it: QtWidgets.QListWidgetItem, q: str) -> None:
        q = (q or "").strip()
        if not q:
            return
        txt = it.text() or ""
        if q.casefold() in txt.casefold():
            f = it.font()
            f.setBold(True)
            it.setFont(f)
            it.setForeground(QtGui.QBrush(QtGui.QColor("#111827")))

    def _open_selected_working(self, item: QtWidgets.QListWidgetItem) -> None:
        pid = item.data(QtCore.Qt.UserRole)
        if isinstance(pid, str) and pid.startswith("p_"):
            self.open_project.emit(pid)

    def _open_selected_export(self, item: QtWidgets.QListWidgetItem) -> None:
        f = item.data(QtCore.Qt.UserRole) or {}
        path = f.get("path") if isinstance(f, dict) else None
        if not path:
            return
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(path))

    def _working_context_menu(self, pos) -> None:
        item = self.lst_working.itemAt(pos)
        if not item:
            return
        pid = item.data(QtCore.Qt.UserRole)
        if not (isinstance(pid, str) and pid.startswith("p_")):
            return

        menu = QtWidgets.QMenu(self)
        act_open = menu.addAction("Open")
        act_rename = menu.addAction("Rename")
        act_delete = menu.addAction("Delete")
        chosen = menu.exec(self.lst_working.mapToGlobal(pos))

        if chosen == act_open:
            self.open_project.emit(pid)
        elif chosen == act_rename:
            self._rename_project(pid)
        elif chosen == act_delete:
            self._confirm_delete_project(pid, item.text())

    def _exported_context_menu(self, pos) -> None:
        item = self.lst_exported.itemAt(pos)
        if not item:
            return
        f = item.data(QtCore.Qt.UserRole)
        if not isinstance(f, dict):
            return

        menu = QtWidgets.QMenu(self)
        act_open = menu.addAction("Open")
        act_info = menu.addAction("Info")
        chosen = menu.exec(self.lst_exported.mapToGlobal(pos))
        if chosen == act_open:
            path = f.get("path")
            if path:
                QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(path))
        elif chosen == act_info:
            QtWidgets.QMessageBox.information(self, "Exported", str(f))

    def _imported_context_menu(self, pos) -> None:
        item = self.lst_imported.itemAt(pos)
        if not item:
            return
        f = item.data(QtCore.Qt.UserRole)
        if not isinstance(f, dict):
            return
        menu = QtWidgets.QMenu(self)
        act_info = menu.addAction("Info")
        chosen = menu.exec(self.lst_imported.mapToGlobal(pos))
        if chosen == act_info:
            QtWidgets.QMessageBox.information(self, "Imported", str(f))

    def _rename_project(self, pid: str) -> None:
        pr = self.ds.get_project(pid)
        if not pr:
            return
        title, ok = QtWidgets.QInputDialog.getText(self, "Rename", "New name:", text=pr.title)
        if not ok:
            return
        title = (title or "").strip()
        if not title:
            self.logger.info("Project rename cancelled: empty title")
            return
        pr.title = self.ds.make_unique_project_title(title, exclude_id=pr.id)
        pr.meta = pr.meta or {}
        pr.meta["named"] = True
        self.ds.update_project(pr)
        self.refresh()

    def _confirm_delete_project(self, pid: str, title: str) -> None:
        btn = QtWidgets.QMessageBox.question(
            self,
            "Delete working page",
            f"Delete '{title}'?\n\nThis cannot be undone.",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        if btn != QtWidgets.QMessageBox.Yes:
            return
        self.ds.delete_project(pid)
        self.refresh()

    # ----------------- words mode -----------------
    def _refresh_words(self, q: str) -> None:
        hits = self.ds.search_words(q, limit=5000)

        # Group by normalized form to avoid duplicates in UI
        by_norm: Dict[str, Any] = {}
        for w in hits:
            norm = getattr(w, "norm", "") or ""
            cur = by_norm.get(norm)
            if cur is None:
                by_norm[norm] = w
                continue

            def score(x) -> tuple:
                return (
                    1 if (getattr(x, "word_nikud", "") or "").strip() else 0,
                    1 if (getattr(x, "hebrew", "") or "").strip() else 0,
                    1 if (getattr(x, "english", "") or "").strip() else 0,
                    len(getattr(x, "sources", []) or []),
                    getattr(x, "created_at", 0.0),
                )

            if score(w) > score(cur):
                by_norm[norm] = w

        rows = list(by_norm.values())

        sort_by = self.cbo_sort_by.currentText()
        desc = self.cbo_sort_order.currentText() == "Desc"

        def word_display(w) -> str:
            return (getattr(w, "word_nikud", "") or "").strip() or (getattr(w, "word_raw", "") or "").strip()

        if sort_by == "English":
            rows.sort(key=lambda w: (getattr(w, "english", "") or "").casefold(), reverse=desc)
        elif sort_by == "Hebrew":
            rows.sort(key=lambda w: (getattr(w, "hebrew", "") or "").casefold(), reverse=desc)
        else:
            rows.sort(key=lambda w: word_display(w).casefold(), reverse=desc)

        qq = (q or "").strip().casefold()
        self.tbl_words.setRowCount(0)
        for w in rows:
            r = self.tbl_words.rowCount()
            self.tbl_words.insertRow(r)

            it_eng = QtWidgets.QTableWidgetItem((getattr(w, "english", "") or "").strip())
            it_heb = QtWidgets.QTableWidgetItem((getattr(w, "hebrew", "") or "").strip())
            it_word = QtWidgets.QTableWidgetItem(word_display(w))
            it_word.setData(QtCore.Qt.UserRole, getattr(w, "id", ""))

            self.tbl_words.setItem(r, 0, it_eng)
            self.tbl_words.setItem(r, 1, it_heb)
            self.tbl_words.setItem(r, 2, it_word)

            if qq:
                hay = " ".join([it_word.text(), it_heb.text(), it_eng.text()]).casefold()
                if qq in hay:
                    for it in (it_eng, it_heb, it_word):
                        f = it.font()
                        f.setBold(True)
                        it.setFont(f)
                        it.setBackground(QtGui.QBrush(QtGui.QColor("#fff7ed")))

    def _selected_word_id(self) -> Optional[str]:
        r = self.tbl_words.currentRow()
        if r < 0:
            return None
        it = self.tbl_words.item(r, 2)  # Word column
        if not it:
            return None
        wid = it.data(QtCore.Qt.UserRole)
        return wid if isinstance(wid, str) else None

    def _edit_word(self) -> None:
        wid = self._selected_word_id()
        if not wid:
            return
        we = self.ds._words.get(wid)
        if not we:
            return

        dlg = _WordEditDialog(
            self,
            existing={
                "word_raw": we.word_raw,
                "word_nikud": we.word_nikud,
                "english": we.english,
                "hebrew": getattr(we, "hebrew", ""),
            },
        )
        if dlg.exec() != QtWidgets.QDialog.Accepted:
            return
        d = dlg.data()

        # Word itself is immutable here; editing it would be "add a new word".
        we.word_nikud = d["word_nikud"]
        we.english = d["english"]
        we.hebrew = d["hebrew"]

        try:
            self.ds.save_all()
        except (IOError, PermissionError, OSError) as e:
            self.logger.error(f"Failed to save word: {e}")
            QtWidgets.QMessageBox.critical(self, "Save Failed", f"Cannot save word: {e}\n\nYour changes were NOT saved.")
            return
        self.refresh()

    def _delete_word(self) -> None:
        wid = self._selected_word_id()
        if not wid:
            return
        if (
            QtWidgets.QMessageBox.question(
                self, "Delete", "Delete this word entry?", QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
            )
            != QtWidgets.QMessageBox.Yes
        ):
            return
        if wid in self.ds._words:
            del self.ds._words[wid]
        try:
            self.ds.save_all()
        except (IOError, PermissionError, OSError) as e:
            self.logger.error(f"Failed to delete word: {e}")
            QtWidgets.QMessageBox.critical(self, "Delete Failed", f"Cannot delete word: {e}\n\nYour changes were NOT saved.")
            return
        self.refresh()

    def _show_word_sources(self) -> None:
        wid = self._selected_word_id()
        if not wid:
            return
        we = self.ds._words.get(wid)
        if not we:
            return
        srcs = list(dict.fromkeys((we.sources or [])))
        msg = "\n".join(f"• {s}" for s in srcs) if srcs else "(no sources)"
        QtWidgets.QMessageBox.information(self, "Sources", msg)

    def _words_context_menu(self, pos) -> None:
        item = self.tbl_words.itemAt(pos)
        if item is None:
            return
        row = item.row()
        if row < 0:
            return
        self.tbl_words.setCurrentCell(row, 2)
        self.tbl_words.selectRow(row)

        menu = QtWidgets.QMenu(self)
        act_edit = menu.addAction("Edit")
        act_del = menu.addAction("Delete")
        act_src = menu.addAction("Sources")
        chosen = menu.exec(self.tbl_words.mapToGlobal(pos))

        if chosen == act_edit:
            self._edit_word()
        elif chosen == act_del:
            self._delete_word()
        elif chosen == act_src:
            self._show_word_sources()


class _WordEditDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, existing: dict | None = None):
        super().__init__(parent)
        self.setWindowTitle("Word")
        self.resize(520, 240)
        existing = existing or {}

        lay = QtWidgets.QVBoxLayout(self)
        form = QtWidgets.QFormLayout()

        self.in_word = QtWidgets.QLineEdit(existing.get("word_raw", ""))
        self.in_word.setReadOnly(True)
        self.in_nikud = QtWidgets.QLineEdit(existing.get("word_nikud", ""))
        self.in_eng = QtWidgets.QLineEdit(existing.get("english", ""))
        self.in_heb = QtWidgets.QLineEdit(existing.get("hebrew", ""))

        form.addRow("Word", self.in_word)
        form.addRow("Nikud", self.in_nikud)
        form.addRow("English", self.in_eng)
        form.addRow("Hebrew", self.in_heb)
        lay.addLayout(form)

        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def data(self) -> dict:
        word_raw = (self.in_word.text() or "").strip()
        if not word_raw:
            raise ValueError("Word cannot be empty")
        return {
            "word_raw": word_raw,
            "word_nikud": (self.in_nikud.text() or "").strip(),
            "english": (self.in_eng.text() or "").strip(),
            "hebrew": (self.in_heb.text() or "").strip(),
        }
