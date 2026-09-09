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
from limes_desktop.views.entity import EntityView
from limes_desktop.views.query_builder import BuilderView
from limes_desktop.views.query_cypher import CypherConsole
from limes_desktop.views.query_history import SavedQueriesPanel
from limes_desktop.views.query_nl import NlqView
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

    def version_label_text(self) -> str:
        return self._version_label.text()

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
        # immediate startup health probe (FR-DC-002): refresh() also starts
        # the 10 s timer when the API answers, and pauses it when unreachable
        self.banner.refresh()
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
        # the entity view (Task 6); Tasks 8-11 replace the remaining placeholders
        self.entity_view = EntityView(state)
        self.stack.addWidget(self.entity_view)
        self.nlq_view = NlqView(state, client_factory=client_factory)
        self.stack.addWidget(self.nlq_view)
        self.cypher_console = CypherConsole(state, client_factory=client_factory)
        self.stack.addWidget(self.cypher_console)
        self.saved_queries_panel = SavedQueriesPanel(
            state,
            client_factory=client_factory,
            current_query=self._current_query,
        )
        self.stack.addWidget(self.saved_queries_panel)
        # Task 8: ontology-driven query builder (FR-DC-031); fetches its
        # schema lazily on first show, never at construction
        self.builder_view = BuilderView(state, client_factory=client_factory)
        self.stack.addWidget(self.builder_view)
        # Task 9: viz views (FR-DC-040..043). The QtWebEngine-dependent view
        # modules are imported here (lazily at construction, NFR-DC-071), so
        # importing this module stays headless-safe; page creation itself
        # happens on first show().
        from limes_desktop.views.viz.map import MapView
        from limes_desktop.views.viz.network import NetworkView
        from limes_desktop.views.viz.timeline import TimelineView

        self.network_view = NetworkView(state)
        self.map_view = MapView(state)
        self.timeline_view = TimelineView(state)
        self.stack.addWidget(self.network_view)
        self.stack.addWidget(self.map_view)
        self.stack.addWidget(self.timeline_view)
        # Task 10: read-only ops views (FR-DC-050/051/052) on pages 8-10
        from limes_desktop.views.ops.ingest import IngestView
        from limes_desktop.views.ops.ledger import LedgerView
        from limes_desktop.views.ops.references import ReferencesView

        self.ingest_view = IngestView(client_factory=client_factory)
        self.ledger_view = LedgerView(client_factory=client_factory)
        self.references_view = ReferencesView(client_factory=client_factory)
        self.stack.addWidget(self.ingest_view)
        self.stack.addWidget(self.ledger_view)
        self.stack.addWidget(self.references_view)
        self.stack.addWidget(QWidget())  # trailing placeholder for Task 11
        self.setCentralWidget(self.stack)

        # result bundles flow into the viz views; expansion goes through the
        # API client (the view itself never fetches — FR-DC-040)
        for viz in (self.network_view, self.map_view, self.timeline_view):
            state.result_arrived.connect(viz.on_result_arrived)
        self.network_view.bridge.expand_requested.connect(self._expand_neighbors)

        state.connection_changed.connect(self._on_connection_changed)

    def _expand_neighbors(self, entity_id: str) -> None:
        try:
            graph = self.banner.client_factory().entity_neighbors(entity_id)
        except (ApiError, ApiUnreachable):
            return
        self.network_view.push_payload(self.network_view.apply_neighbors(entity_id, graph))

    def _current_query(self) -> tuple[str, str]:
        """The (surface, query text) of the active query surface, for saving."""
        current = self.stack.currentWidget()
        if current is self.cypher_console:
            return "cypher", self.cypher_console.editor.toPlainText()
        if current is self.nlq_view:
            return "nlq", self.nlq_view.cypher_edit.toPlainText()
        return "", ""

    def refresh_banner(self) -> None:
        self.banner.refresh()

    def _on_connection_changed(self, profile: object) -> None:
        if isinstance(profile, ConnectionProfile):
            self.banner._profile_label.setText(f"{profile.name} {profile.base_url}")
        else:
            self.banner._profile_label.setText("disconnected")
        # the client factory rebinds to the new profile's base_url before this
        # handler runs (connection order in __main__); probe the new endpoint now
        self.banner.refresh()

    def _run_search(self, query: str) -> None:
        try:
            hits = self.banner.client_factory().search(query)
        except (ApiError, ApiUnreachable):
            return
        self._state.publish(
            QueryOutcomeBundle(result=hits, coverage=None, source="search")
        )
