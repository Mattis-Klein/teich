from __future__ import annotations
from PySide6 import QtWidgets, QtCore

from ..widgets import Card, TopBar
from ..store import DataStore


class BrowsePage(QtWidgets.QWidget):
    open_project = QtCore.Signal(str)

    def __init__(self, ds: DataStore, parent=None):
        super().__init__(parent)
        self.ds = ds
        self.mode = "files"  # files | words

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(12)

        top = TopBar("Browse")
        outer.addWidget(top)

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

        # Content area
        self.card = Card()
        content = QtWidgets.QVBoxLayout(self.card)
        content.setContentsMargins(14, 14, 14, 14)
        content.setSpacing(12)

        # --- Files view widgets (3 sections)
        self.files_widget = QtWidgets.QWidget()
        fw = QtWidgets.QVBoxLayout(self.files_widget)
        fw.setContentsMargins(0, 0, 0, 0)
        fw.setSpacing(12)

        # Recent section
        recent_box = QtWidgets.QGroupBox("Recent")
        rlay = QtWidgets.QVBoxLayout(recent_box)
        self.lst_recent = QtWidgets.QListWidget()
        self.lst_recent.setObjectName("listClean")
        rlay.addWidget(self.lst_recent)
        fw.addWidget(recent_box)

        # All files split
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
            lay.addWidget(lst)
            return lst

        self.lst_imported = mk_list(self.grp_imported)
        self.lst_working = mk_list(self.grp_working)
        self.lst_saved = mk_list(self.grp_saved)

        alay.addWidget(self.grp_imported, 1)
        alay.addWidget(self.grp_working, 1)
        alay.addWidget(self.grp_saved, 1)

        fw.addWidget(all_box, 2)

        # --- Words view widgets
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
        self.tbl_words.setAlternatingRowColors(True)
        self.tbl_words.setObjectName("mainTable")
        self.tbl_words.setColumnWidth(0, 220)
        self.tbl_words.setColumnWidth(1, 220)
        ww.addWidget(self.tbl_words, 1)

        content.addWidget(self.files_widget)
        content.addWidget(self.words_widget)

        outer.addWidget(self.card, 1)

        # Signals
        self.btn_files.clicked.connect(lambda: self._set_mode("files"))
        self.btn_words.clicked.connect(lambda: self._set_mode("words"))
        self.search.textChanged.connect(lambda _t: self.refresh())

        self.lst_working.itemDoubleClicked.connect(self._open_selected_working)
        self.lst_recent.itemDoubleClicked.connect(self._open_selected_recent)

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

    def refresh(self) -> None:
        q = (self.search.text() or "").strip()

        if self.mode == "words":
            self._refresh_words(q)
            return

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

        def match(item_title: str) -> bool:
            if not q:
                return True
            return q.lower() in (item_title or "").lower()

        # Recent list: show created/imported/export items
        for f in recent:
            title = f.get("title", "")
            if not match(title):
                continue
            it = QtWidgets.QListWidgetItem(title)
            it.setData(QtCore.Qt.UserRole, f)
            self.lst_recent.addItem(it)

        # Imported from files registry
        for f in all_files:
            if f.get("kind") != "import":
                continue
            title = f.get("title", "")
            if not match(title):
                continue
            it = QtWidgets.QListWidgetItem(title)
            it.setData(QtCore.Qt.UserRole, f)
            self.lst_imported.addItem(it)

        # Working pages from projects
        for pr in projects:
            # A project is considered "working" unless explicitly marked closed.
            closed = bool((pr.meta or {}).get("closed"))
            if closed:
                continue
            if not match(pr.title):
                continue
            it = QtWidgets.QListWidgetItem(pr.title)
            it.setData(QtCore.Qt.UserRole, pr.id)
            self.lst_working.addItem(it)

        # Saved/Exported from files registry
        for f in all_files:
            if f.get("kind") != "export":
                continue
            title = f.get("title", "")
            if not match(title):
                continue
            fmt = f.get("format", "")
            label = f"{title} ({fmt})" if fmt else title
            it = QtWidgets.QListWidgetItem(label)
            it.setData(QtCore.Qt.UserRole, f)
            self.lst_saved.addItem(it)

        # Empty-state hints (clean, no symbols)
        if self.lst_imported.count() == 0:
            self.lst_imported.addItem(QtWidgets.QListWidgetItem("No imported items yet."))
            self.lst_imported.item(0).setFlags(QtCore.Qt.NoItemFlags)
        if self.lst_working.count() == 0:
            self.lst_working.addItem(QtWidgets.QListWidgetItem("No working pages yet."))
            self.lst_working.item(0).setFlags(QtCore.Qt.NoItemFlags)
        if self.lst_saved.count() == 0:
            self.lst_saved.addItem(QtWidgets.QListWidgetItem("No saved/exported files yet."))
            self.lst_saved.item(0).setFlags(QtCore.Qt.NoItemFlags)

    def _open_selected_working(self, item: QtWidgets.QListWidgetItem) -> None:
        pid = item.data(QtCore.Qt.UserRole)
        if isinstance(pid, str) and pid.startswith("p_"):
            self.open_project.emit(pid)

    def _open_selected_recent(self, item: QtWidgets.QListWidgetItem) -> None:
        f = item.data(QtCore.Qt.UserRole) or {}
        if f.get("kind") == "project":
            self.open_project.emit(f.get("id", ""))

    # ---------- words mode ----------

    def _refresh_words(self, q: str) -> None:
        rows = self.ds.search_words(q, limit=80)
        self.tbl_words.setRowCount(0)
        for w in rows:
            r = self.tbl_words.rowCount()
            self.tbl_words.insertRow(r)
            self.tbl_words.setItem(r, 0, QtWidgets.QTableWidgetItem(w.word_raw))
            self.tbl_words.setItem(r, 1, QtWidgets.QTableWidgetItem(w.word_nikud))
            self.tbl_words.setItem(r, 2, QtWidgets.QTableWidgetItem(w.english))
