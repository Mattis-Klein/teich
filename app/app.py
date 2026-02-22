from __future__ import annotations
from pathlib import Path
import time

from PySide6 import QtWidgets, QtCore

from .theme import app_stylesheet
from .store import DataStore
from .import_ods import import_ods_words

from .pages.home import HomePage
from .pages.create import CreatePage
from .pages.browse import BrowsePage
from .widgets import PlaceholderPage


class AppWindow(QtWidgets.QMainWindow):
    def __init__(self, project_root: Path):
        super().__init__()
        self.project_root = project_root

        self.setWindowTitle("Teich — Sukkah Sample")
        self.resize(1120, 780)

        self.ds = DataStore(project_root / "data" / "store")
        # Auto-import sample ODS once (Browse → Words should work immediately)
        ods_dir = project_root / "data" / "ods"
        ods_files = list(ods_dir.glob("*.ods"))
        if ods_files:
            import_ods_words(self.ds, ods_files[0])
        else:
            print(f"[WARN] No .ods file found in {ods_dir}")


        root = QtWidgets.QWidget()
        root.setObjectName("AppRoot")
        self.setCentralWidget(root)

        self.stack = QtWidgets.QStackedLayout(root)

        self.page_home = HomePage()
        self.page_browse = BrowsePage(self.ds)
        self.page_create = CreatePage(self.ds, project_root)

        self.page_import = PlaceholderPage("Import", "Import — coming soon")
        self.page_settings = PlaceholderPage("Settings", "Settings — coming soon")

        self.stack.addWidget(self.page_home)
        self.stack.addWidget(self.page_browse)
        self.stack.addWidget(self.page_create)
        self.stack.addWidget(self.page_import)
        self.stack.addWidget(self.page_settings)

        self._set_page(self.page_home)

        # Home routing
        self.page_home.new_page.connect(self._new_working_page)
        self.page_home.go_browse.connect(lambda: self._set_page(self.page_browse))
        self.page_home.go_import.connect(lambda: self._set_page(self.page_import))
        self.page_home.go_settings.connect(lambda: self._set_page(self.page_settings))

        # Browse routing
        self.page_browse.open_project.connect(self._open_project)

        # Create routing
        self.page_create.back.connect(self._back_from_create)

        # Apply theme
        self.setStyleSheet(app_stylesheet())

    def _set_page(self, w: QtWidgets.QWidget) -> None:
        self.stack.setCurrentWidget(w)

    def _new_working_page(self) -> None:
        # No naming required up front.
        title = f"Working Page — {time.strftime('%Y-%m-%d %H:%M:%S')}"
        pr = self.ds.create_project(title)
        self.page_create.set_project(pr)
        self._set_page(self.page_create)

    def _open_project(self, pid: str) -> None:
        pr = self.ds.get_project(pid)
        if not pr:
            return
        self.page_create.set_project(pr)
        self._set_page(self.page_create)

    def _back_from_create(self) -> None:
        # Back goes to Browse (working pages list lives there).
        self.page_browse.refresh()
        self._set_page(self.page_browse)


def run(project_root: Path) -> None:
    app = QtWidgets.QApplication([])
    win = AppWindow(project_root)
    win.show()
    app.exec()
