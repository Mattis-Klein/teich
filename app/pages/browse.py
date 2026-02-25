from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from ..store import DataStore
from ..widgets import Card, TopBar


class BrowsePage(QtWidgets.QWidget):
    open_project = QtCore.Signal(str)
    go_home = QtCore.Signal()

    def __init__(self, ds: DataStore, parent=None):
        super().__init__(parent)
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

        # Words toolbar
        self.words_toolbar = QtWidgets.QHBoxLayout()
        self.btn_add_word = QtWidgets.QPushButton("Add")
        self.btn_edit_word = QtWidgets.QPushButton("Edit")
        self.btn_del_word = QtWidgets.QPushButton("Delete")
        for b in (self.btn_add_word, self.btn_edit_word, self.btn_del_word):
            b.setFixedHeight(34)
            b.setCursor(QtCore.Qt.PointingHandCursor)
        self.words_toolbar.addWidget(self.btn_add_word)
        self.words_toolbar.addWidget(self.btn_edit_word)
        self.words_toolbar.addWidget(self.btn_del_word)
        self.words_toolbar.addStretch(1)
        outer.addLayout(self.words_toolbar)

        # Content
        self.card = Card()
        content = QtWidgets.QVBoxLayout(self.card)
        content.setContentsMargins(14, 14, 14, 14)
        content.setSpacing(12)

        # -------- Files view
        self.files_widget = QtWidgets.QWidget()
        fw = QtWidgets.QVBoxLayout(self.files_widget)
        fw.setContentsMargins(0, 0, 0, 0)
        fw.setSpacing(12)

        # Recent
        recent_box = QtWidgets.QGroupBox("Recent")
        rlay = QtWidgets.QVBoxLayout(recent_box)
        self.lst_recent = QtWidgets.QListWidget()
        self.lst_recent.setObjectName("listClean")
        self.lst_recent.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.lst_recent.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        rlay.addWidget(self.lst_recent)
        fw.addWidget(recent_box)

        # All / split
        all_box = QtWidgets.QGroupBox("All")
        alay = QtWidgets.QHBoxLayout(all_box)
        alay.setSpacing(12)

        self.grp_imported = QtWidgets.QGroupBox("Imported")
        self.grp_working = QtWidgets.QGroupBox("Working Pages")
        self.grp_saved = QtWidgets.QGroupBox("Files (Saved / Exported)")

        def mk_list(group: QtWidgets.QGroupBox) -> QtWidgets.QListWidget:
            lay = QtWidgets.QVBoxLayout(group)
            lay.setContentsMargins(10, 10, 10, 10)
            lst = QtWidgets.QListWidget()
            lst.setObjectName("listClean")
            lst.setFrameShape(QtWidgets.QFrame.NoFrame)
            lst.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
            return lst

        self.lst_imported = mk_list(self.grp_imported)
        self.lst_working = mk_list(self.grp_working)
        self.lst_saved = mk_list(self.grp_saved)

        # Put lists into group layouts
        QtWidgets.QVBoxLayout(self.grp_imported).addWidget(self.lst_imported)
        QtWidgets.QVBoxLayout(self.grp_working).addWidget(self.lst_working)
        QtWidgets.QVBoxLayout(self.grp_saved).addWidget(self.lst_saved)

        alay.addWidget(self.grp_imported, 1)
        alay.addWidget(self.grp_working, 1)
        alay.addWidget(self.grp_saved, 1)
        fw.addWidget(all_box, 2)

        # Right-click: delete working page (only on right-click, only on item)
        self.lst_working.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.lst_working.customContextMenuRequested.connect(self._working_context_menu)

        # -------- Words view
        self.words_widget = QtWidgets.QWidget()
        ww = QtWidgets.QVBoxLayout(self.words_widget)
        ww.setContentsMargins(0, 0, 0, 0)
        ww.setSpacing(10)

        self.words_hint = QtWidgets.QLabel("Search words imported from your ODS.")
        self.words_hint.setObjectName("muted")
        ww.addWidget(self.words_hint)

        self.tbl_words = QtWidgets.QTableWidget(0, 3)
        self.tbl_words.setHorizontalHeaderLabels(["Word", "Nikud", "English"])
        self.tbl_words.horizontalHeader().setStretchLastSection(True)
        self.tbl_words.verticalHeader().setVisible(False)
        self.tbl_words.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.tbl_words.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.tbl_words.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.tbl_words.setAlternatingRowColors(True)
        self.tbl_words.setObjectName("mainTable")
        self.tbl_words.setColumnWidth(0, 220)
        self.tbl_words.setColumnWidth(1, 220)
        ww.addWidget(self.tbl_words, 1)

        # ✅ Words context menu: ONLY appears on right-click; ONLY if a row is clicked.
        self.tbl_words.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.tbl_words.customContextMenuRequested.connect(self._words_context_menu)

        content.addWidget(self.files_widget)
        content.addWidget(self.words_widget)
        outer.addWidget(self.card, 1)

        # Wire signals
        self.btn_files.clicked.connect(lambda: self._set_mode("files"))
        self.btn_words.clicked.connect(lambda: self._set_mode("words"))
        self.search.textChanged.connect(lambda _t: self.refresh())

        self.lst_working.itemDoubleClicked.connect(self._open_selected_working)
        self.lst_recent.itemDoubleClicked.connect(self._open_selected_recent)

        self.btn_add_word.clicked.connect(self._add_word)
        self.btn_edit_word.clicked.connect(self._edit_word)
        self.btn_del_word.clicked.connect(self._delete_word)

        self.refresh()
        self._apply_mode()

    def _set_mode(self, mode: str) -> None:
        self.mode = mode
        self.btn_files.setChecked(mode == "files")
        self.btn_words.setChecked(mode == "words")
        self._apply_mode()
        self.refresh()

    def _apply_mode(self) -> None:
        self.files_widget.setVisible(self.mode == "files")
        self.words_widget.setVisible(self.mode == "words")
        for i in range(self.words_toolbar.count()):
            w = self.words_toolbar.itemAt(i).widget()
            if w:
                w.setVisible(self.mode == "words")

    def refresh(self) -> None:
        q = (self.search.text() or "").strip()
        if self.mode == "words":
            self._refresh_words(q)
        else:
            self._refresh_files(q)

    # ---------- files mode ----------
    def _refresh_files(self, q: str) -> None:
        self.lst_recent.clear()
        self.lst_imported.clear()
        self.lst_working.clear()
        self.lst_saved.clear()

        recent = self.ds.list_recent_files(limit=10)
        all_files = self.ds.list_files()
        projects = self.ds.list_projects()

        def match_title(item_title: str) -> bool:
            if not q:
                return True
            return q.lower() in (item_title or "").lower()

        def match_project(pr) -> bool:
            if not q:
                return True
            qq = q.lower()
            if qq in (pr.title or "").lower():
                return True
            # also search within explanations/words
            for r in (pr.rows or []):
                if qq in (r.get("word", "") or "").lower() or qq in (r.get("explanation", "") or "").lower():
                    return True
            return False

        # Recent
        for f in recent:
            title = f.get("title", "")
            if not match_title(title):
                continue
            it = QtWidgets.QListWidgetItem(title)
            it.setData(QtCore.Qt.UserRole, f)
            self.lst_recent.addItem(it)
            self._maybe_bold_item(self.lst_recent, it, q)

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
            self._maybe_bold_item(self.lst_imported, it, q)

        # Working projects
        for pr in projects:
            closed = bool((pr.meta or {}).get("closed"))
            if closed:
                continue
            if not match_project(pr):
                continue
            it = QtWidgets.QListWidgetItem(pr.title)
            it.setData(QtCore.Qt.UserRole, pr.id)
            self.lst_working.addItem(it)
            self._maybe_bold_item(self.lst_working, it, q)

        # Saved/Exported
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
            self.lst_saved.addItem(it)
            self._maybe_bold_item(self.lst_saved, it, q)

        # Empty states
        if self.lst_imported.count() == 0:
            it = QtWidgets.QListWidgetItem("No imported items yet.")
            it.setFlags(QtCore.Qt.NoItemFlags)
            self.lst_imported.addItem(it)
        if self.lst_working.count() == 0:
            it = QtWidgets.QListWidgetItem("No working pages yet.")
            it.setFlags(QtCore.Qt.NoItemFlags)
            self.lst_working.addItem(it)
        if self.lst_saved.count() == 0:
            it = QtWidgets.QListWidgetItem("No saved/exported files yet.")
            it.setFlags(QtCore.Qt.NoItemFlags)
            self.lst_saved.addItem(it)

    def _maybe_bold_item(self, lw: QtWidgets.QListWidget, it: QtWidgets.QListWidgetItem, q: str) -> None:
        """Bold ONLY the matched substring (the letters you typed)."""
        q = (q or "").strip()
        if not q:
            return
        txt = it.text() or ""
        low = txt.lower()
        qlow = q.lower()
        idx = low.find(qlow)
        if idx < 0:
            return
        hi = txt[idx : idx + len(q)]

        # RichText QLabel replaces the default item text.
        html = txt[:idx] + "<b>" + hi + "</b>" + txt[idx + len(q) :]
        lbl = QtWidgets.QLabel(html)
        lbl.setTextFormat(QtCore.Qt.RichText)
        lbl.setContentsMargins(6, 2, 6, 2)
        lw.setItemWidget(it, lbl)

    def _open_selected_working(self, item: QtWidgets.QListWidgetItem) -> None:
        pid = item.data(QtCore.Qt.UserRole)
        if isinstance(pid, str) and pid.startswith("p_"):
            self.open_project.emit(pid)

    def _open_selected_recent(self, item: QtWidgets.QListWidgetItem) -> None:
        f = item.data(QtCore.Qt.UserRole) or {}
        if f.get("kind") == "project":
            self.open_project.emit(f.get("id", ""))

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

    # ---------- words mode ----------
    def _refresh_words(self, q: str) -> None:
        rows = self.ds.search_words(q, limit=2000)
        rows.sort(key=lambda w: (w.norm, w.word_raw))

        self.tbl_words.setRowCount(0)
        for w in rows:
            r = self.tbl_words.rowCount()
            self.tbl_words.insertRow(r)
            it0 = QtWidgets.QTableWidgetItem(w.word_raw)
            it0.setData(QtCore.Qt.UserRole, w.id)
            self.tbl_words.setItem(r, 0, it0)
            self.tbl_words.setItem(r, 1, QtWidgets.QTableWidgetItem(w.word_nikud))
            self.tbl_words.setItem(r, 2, QtWidgets.QTableWidgetItem(w.english))

    def _selected_word_id(self) -> str | None:
        r = self.tbl_words.currentRow()
        if r < 0:
            return None
        it = self.tbl_words.item(r, 0)
        if not it:
            return None
        return it.data(QtCore.Qt.UserRole)

    def _add_word(self) -> None:
        dlg = _WordEditDialog(self)
        if dlg.exec() != QtWidgets.QDialog.Accepted:
            return
        try:
            d = dlg.data()
        except ValueError as e:
            QtWidgets.QMessageBox.warning(self, "Invalid Input", str(e))
            self._add_word()  # Reopen dialog for correction
            return
        self.ds.upsert_word(
            word_raw=d["word_raw"],
            word_nikud=d["word_nikud"],
            english=d["english"],
            hebrew=d["hebrew"],
            source="manual",
        )
        self.ds.save_all()
        self.refresh()

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
        try:
            d = dlg.data()
        except ValueError as e:
            QtWidgets.QMessageBox.warning(self, "Invalid Input", str(e))
            return  # User must retry from word list
        we.word_raw = d["word_raw"]
        we.word_nikud = d["word_nikud"]
        we.english = d["english"]
        we.hebrew = d["hebrew"]
        self.ds.save_all()
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
        self.ds.save_all()
        self.refresh()

    def _words_context_menu(self, pos) -> None:
        # ✅ Only show menu if right-click is on an actual row.
        item = self.tbl_words.itemAt(pos)
        if item is None:
            return
        row = item.row()
        if row < 0:
            return
        self.tbl_words.setCurrentCell(row, 0)
        self.tbl_words.selectRow(row)

        menu = QtWidgets.QMenu(self)
        act_add = menu.addAction("Add")
        act_edit = menu.addAction("Edit")
        act_del = menu.addAction("Delete")
        chosen = menu.exec(self.tbl_words.mapToGlobal(pos))

        if chosen == act_add:
            self._add_word()
        elif chosen == act_edit:
            self._edit_word()
        elif chosen == act_del:
            self._delete_word()


class _WordEditDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, existing: dict | None = None):
        super().__init__(parent)
        self.setWindowTitle("Word")
        self.resize(520, 240)
        existing = existing or {}

        lay = QtWidgets.QVBoxLayout(self)
        form = QtWidgets.QFormLayout()

        self.in_word = QtWidgets.QLineEdit(existing.get("word_raw", ""))
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
