# desktop/src/limes_desktop/views/main_window.py | v0.1.0 | app shell: dock, views, banner
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDockWidget,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QStackedWidget,
    QToolBar,
    QWidget,
)

from limes_desktop.api.errors import ApiError, ApiUnreachable
from limes_desktop.config import ConnectionProfile, ProfileStore
from limes_desktop.state import QueryOutcomeBundle, SessionState
from limes_desktop.views.search import SearchBar

BannerState = str  # "ok" | "degraded" | "unreachable"

REFRESH_INTERVAL_MS = 10_000


class _ConnectionBanner(QFrame):
    """Green/amber/red pill + profile + API version; 10 s QTimer refresh (§4)."""

    def __init__(self, client_factory: Callable[[], Any]) -> None:
        super().__init__()
        self.client_factory = client_factory
        self._unreachable = False
        self._status = "unreachable"
        self._version = ""

        self._pill = QLabel(self)
        self._profile_label = QLabel("disconnected", self)
        self._version_label = QLabel("", self)

        row = QHBoxLayout(self)
        row.addWidget(self._pill)
        row.addWidget(self._profile_label)
        row.addStretch(1)
        row.addWidget(self._version_label)

        self._timer = QTimer(self)
        self._timer.setInterval(REFRESH_INTERVAL_MS)
        self._timer.timeout.connect(lambda: self.refresh())

        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._render()

    # -- seams ---------------------------------------------------------------

    def status_text(self) -> str:
        return self._status

    def is_unreachable(self) -> bool:
        return self._unreachable

    def profile_label_text(self) -> str:
        return self._profile_label.text()

    def refresh(self) -> None:
        """One health probe; safe to call directly from tests (no timer wait)."""
        try:
            info = self.client_factory().health()
        except ApiUnreachable:
            self._unreachable = True
            self._status = "unreachable"
            self._version = ""
        except ApiError:
            self._unreachable = True
            self._status = "degraded"
            self._version = ""
        else:
            self._unreachable = False
            self._status = info.status
            self._version = info.ontology_version
        # pause the timer while unreachable (§4); resume when healthy again
        if self._unreachable:
            self._timer.stop()
        elif not self._timer.isActive():
            self._timer.start()
        self._render()

    # -- rendering -----------------------------------------------------------

    def _render(self) -> None:
        colors = {"ok": "#2e7d32", "degraded": "#f9a825", "unreachable": "#c62828"}
        self._pill.setStyleSheet(
            f"background-color: {colors.get(self._status, '#c62828')};"
            "border-radius: 8px; color: white; padding: 2px 10px;"
        )
        self._pill.setText(self._status)
        self._version_label.setText(
            f"ontology {self._version}" if self._version else ""
        )


class MainWindow(QMainWindow):
    """Shell: left dock = search, central = stacked placeholder views, top = banner."""

    def __init__(
        self,
        state: SessionState,
        profile_store: ProfileStore | None,
        client_factory: Callable[[], Any],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("LIMES")
        self._state = state

        self.banner = _ConnectionBanner(client_factory)
        self.banner._timer.start()
        self._toolbar = QToolBar("connection", self)
        self._toolbar.setMovable(False)
        self._toolbar.addWidget(self.banner)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self._toolbar)

        self.search_bar = SearchBar(state)
        self.search_bar.search_submitted.connect(self._run_search)
        dock = QDockWidget("Search", self)
        dock.setWidget(self.search_bar)
        dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)

        self.stack = QStackedWidget(self)
        # placeholders; Tasks 7-11 replace them
        for _ in range(3):
            self.stack.addWidget(QWidget())
        self.setCentralWidget(self.stack)

        state.connection_changed.connect(self._on_connection_changed)

    def _banner_toolbar(self) -> QToolBar:
        return self._toolbar

    def refresh_banner(self) -> None:
        self.banner.refresh()

    def _on_connection_changed(self, profile: object) -> None:
        if isinstance(profile, ConnectionProfile):
            self.banner._profile_label.setText(f"{profile.name} {profile.base_url}")
        else:
            self.banner._profile_label.setText("disconnected")

    def _run_search(self, query: str) -> None:
        try:
            hits = self.banner.client_factory().search(query)
        except (ApiError, ApiUnreachable):
            return
        self._state.publish(
            QueryOutcomeBundle(result=hits, coverage=None, source="search")
        )
