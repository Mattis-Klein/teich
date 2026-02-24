from __future__ import annotations
from pathlib import Path
import time
from PySide6 import QtWidgets
from .theme import app_stylesheet
from .store import DataStore
from .import_ods import import_ods_words
from .pages.home import HomePage
from .pages.browse import BrowsePage
from .pages.create_picker import CreatePickerPage
from .pages.create_editor import CreateEditorPage
from .pages.export_page import ExportPage
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
        # Create flow is now *two real pages*
        self.page_create_picker = CreatePickerPage(self.ds, project_root)
        self.page_create_editor = CreateEditorPage(self.ds, project_root)
        self.page_export = ExportPage(self.ds)
        self.page_import = PlaceholderPage("Import", "Import — coming soon")
        self.page_settings = PlaceholderPage("Settings", "Settings — coming soon")
        self.stack.addWidget(self.page_home)
        self.stack.addWidget(self.page_browse)
        self.stack.addWidget(self.page_create_picker)
        self.stack.addWidget(self.page_create_editor)
        self.stack.addWidget(self.page_export)
        self.stack.addWidget(self.page_import)
        self.stack.addWidget(self.page_settings)
        # navigation history (Back behaves like a stack)
        self._nav_stack: list[QtWidgets.QWidget] = []
        self._set_root(self.page_home)
        # Home routing
        self.page_home.new_page.connect(self._new_working_page)
        self.page_home.go_browse.connect(lambda: self._push_page(self.page_browse))
        self.page_home.go_import.connect(lambda: self._push_page(self.page_import))
        self.page_home.go_settings.connect(lambda: self._push_page(self.page_settings))
        # Browse routing
        self.page_browse.open_project.connect(self._open_project)
        self.page_browse.go_home.connect(self.go_back)
        # Create Picker routing
        self.page_create_picker.back_to_browse.connect(self.go_back)
        self.page_create_picker.generateRequested.connect(self._to_create_editor)
        # Create Editor routing
        self.page_create_editor.back_to_picker.connect(self.go_back)
        self.page_create_editor.saved.connect(self._on_editor_saved)
        self.page_create_editor.exportRequested.connect(self._to_export)

        # Export routing
        self.page_export.back_to_editor.connect(self.go_back)
        # Placeholder routing
        self.page_import.back.connect(self.go_back)
        self.page_settings.back.connect(self.go_back)
        # Apply theme
        self.setStyleSheet(app_stylesheet())
    def _set_page(self, w: QtWidgets.QWidget) -> None:
        self.stack.setCurrentWidget(w)
    def _set_root(self, w: QtWidgets.QWidget) -> None:
        """Go to a page and clear history."""
        self._nav_stack = []
        self._set_page(w)
    def _push_page(self, w: QtWidgets.QWidget) -> None:
        """Navigate to a page, remembering current page for Back."""
        cur = self.stack.currentWidget()
        if cur is not None:
            self._nav_stack.append(cur)
        self._set_page(w)
    def _confirm_leave_if_dirty(self) -> bool:
        """Return True if navigation should continue, False if canceled."""
        cur = self.stack.currentWidget()
        if cur and hasattr(cur, "is_dirty") and callable(getattr(cur, "is_dirty")):
            try:
                dirty = bool(cur.is_dirty())
            except Exception:
                dirty = False
            if dirty:
                choice = QtWidgets.QMessageBox.question(
                    self,
                    "Unsaved changes",
                    "You have unsaved changes that will be lost if you close.\n\nDo you want to save before closing?",
                    QtWidgets.QMessageBox.Save | QtWidgets.QMessageBox.Discard | QtWidgets.QMessageBox.Cancel,
                    QtWidgets.QMessageBox.Save,
                )
                if choice == QtWidgets.QMessageBox.Cancel:
                    return False
                if choice == QtWidgets.QMessageBox.Save:
                    if hasattr(cur, "save_now") and callable(getattr(cur, "save_now")):
                        cur.save_now()
        return True
    def go_back(self) -> None:
        if not self._confirm_leave_if_dirty():
            return
        if self._nav_stack:
            prev = self._nav_stack.pop()
            # When leaving picker, refresh browse if needed
            if prev is self.page_browse:
                self.page_browse.refresh()
            self._set_page(prev)
        else:
            self._set_root(self.page_home)
    def closeEvent(self, event):
        if not self._confirm_leave_if_dirty():
            event.ignore()
            return
        event.accept()
    # ----- create flow
    def _new_working_page(self) -> None:
        title = f"Working Page — {time.strftime('%Y-%m-%d %H:%M:%S')}"
        pr = self.ds.create_project(title)
        self.page_create_picker.set_project(pr)
        self.page_create_editor.set_project(pr)
        self._push_page(self.page_create_picker)
    def _open_project(self, pid: str) -> None:
        pr = self.ds.get_project(pid)
        if not pr:
            return
        self.page_create_editor.set_project(pr)
        # Open workspace directly (Browse -> open)
        self._push_page(self.page_create_editor)
    def _to_create_editor(self, selection) -> None:
        # selection is app.models.selection.Selection
        self.page_create_editor.load_selection(selection)
        self._push_page(self.page_create_editor)

    def _to_export(self, project_id: str) -> None:
        pr = self.ds.get_project(project_id)
        if not pr:
            return
        self.page_export.set_project(pr)
        self._push_page(self.page_export)
    def _on_editor_saved(self) -> None:
        # refresh browse lists to reflect updated title/time
        self.page_browse.refresh()
    def _back_from_create_picker(self) -> None:
        # kept for backward compat; use go_back()
        self.go_back()
def run(project_root: Path) -> None:
    app = QtWidgets.QApplication([])
    win = AppWindow(project_root)
    win.show()
    app.exec()