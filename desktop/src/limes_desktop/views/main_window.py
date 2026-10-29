# desktop/src/limes_desktop/views/main_window.py | v0.1.0 | app shell: dock, views, banner
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Qt, QThreadPool, QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QDockWidget,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QToolBar,
    QWidget,
)

from limes_desktop.api.errors import ApiError, ApiUnreachable
from limes_desktop.config import ConnectionProfile, ProfileStore
from limes_desktop.state import QueryOutcomeBundle, SessionState, TemporalFilter
from limes_desktop.views.coverage_panel import CoveragePanel
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

    checked = Signal(object)

    def __init__(self, client_factory: Callable[[], Any]) -> None:
        super().__init__()
        self.client_factory = client_factory
        self._generation = 0
        self._tasks: dict[int, Any] = {}
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
        self._timer.timeout.connect(self.refresh_async)

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
        """Synchronous explicit seam; ordinary startup/timer probes are asynchronous."""
        from limes_desktop.connection_probe import probe

        self._generation += 1
        try:
            result = probe(self.client_factory())
        except (ApiError, ApiUnreachable, ValueError):
            result = {"status": "unreachable", "version": ""}
        self._receive(self._generation, result)

    def refresh_async(self) -> None:
        from limes_desktop.connection_probe import ConnectionProbe

        if self._generation in self._tasks:
            return
        self._generation += 1
        try:
            client = self.client_factory()  # session credential prompt belongs to GUI thread
        except (ApiError, ApiUnreachable, ValueError):
            self._receive(self._generation, {"status": "unreachable", "version": ""})
            return
        task = ConnectionProbe(self._generation, client)
        self._tasks[self._generation] = task
        task.signals.completed.connect(self._receive)
        QThreadPool.globalInstance().start(task)

    @Slot(int, object)
    def _receive(self, generation: int, result: dict[str, Any]) -> None:
        self._tasks.pop(generation, None)
        if generation != self._generation:
            return
        self._status = result["status"]
        self._version = result["version"]
        self._unreachable = self._status != "ok"
        # Keep probing during outages so recovery is visible without a restart.
        self._timer.start()
        self._render()
        self.checked.emit(result)

    # -- rendering -----------------------------------------------------------

    def _render(self) -> None:
        colors = {"ok": "#2e7d32", "degraded": "#f9a825", "unreachable": "#c62828"}
        self._pill.setStyleSheet(
            f"background-color: {colors.get(self._status, '#c62828')};"
            "border-radius: 8px; color: white; padding: 2px 10px;"
        )
        self._pill.setText(self._status)
        self._version_label.setText(f"ontology {self._version}" if self._version else "")


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
        self._profile_store = profile_store

        self.banner = _ConnectionBanner(client_factory)
        # Startup probes run after the window can paint and never block search.
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

        # FR-DC-034/AC-DC-3: one shared coverage panel across all query
        # surfaces; the panel self-connects to result_arrived in __init__
        self.coverage_panel = CoveragePanel(state)
        coverage_dock = QDockWidget("Coverage", self)
        coverage_dock.setWidget(self.coverage_panel)
        coverage_dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, coverage_dock)

        self.stack = QStackedWidget(self)
        # the entity view (Task 6); Tasks 8-11 replace the remaining placeholders
        self.entity_view = EntityView(state, client_factory=client_factory)
        self.stack.addWidget(self.entity_view)
        self.nlq_view = NlqView(state, client_factory=client_factory)
        self.stack.addWidget(self.nlq_view)
        self.cypher_console = CypherConsole(state, client_factory=client_factory)
        self.stack.addWidget(self.cypher_console)
        self._query_source: QWidget = self.cypher_console
        self.stack.currentChanged.connect(self._remember_query_surface)
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
        # Task 11: backup action (FR-DC-060..063) on page 11; the view imports
        # are local so importing this module stays headless-safe
        from limes_desktop.backup_runner import BackupRunner
        from limes_desktop.views.backup import BackupDialog

        self.backup_runner = BackupRunner(client_factory=client_factory, parent=self)
        from PySide6.QtWidgets import QApplication

        application = QApplication.instance()
        if application is not None:
            application.aboutToQuit.connect(self.backup_runner.close)
        self.backup_dialog = BackupDialog(self.backup_runner, parent=self)
        self.stack.addWidget(self.backup_dialog)
        from PySide6.QtGui import QAction

        from limes_desktop.views.news import NewsView

        self.news_view = NewsView(client_factory, self)
        self.stack.addWidget(self.news_view)
        news_action = QAction("Investigations and news", self)
        news_action.triggered.connect(lambda: self.stack.setCurrentWidget(self.news_view))
        self.menuBar().addAction(news_action)
        state.selection_changed.connect(
            lambda value: setattr(self.news_view, "selected_entity", value)
        )
        self.entity_view.assertion_selected.connect(
            lambda value: setattr(self.news_view, "selected_relation", value)
        )
        navigation = self.menuBar().addMenu("Views")
        for view, title in (
            (self.entity_view, "Entity"),
            (self.nlq_view, "Natural language"),
            (self.cypher_console, "Cypher console"),
            (self.saved_queries_panel, "Saved queries"),
            (self.builder_view, "Query builder"),
            (self.network_view, "Network"),
            (self.map_view, "Map"),
            (self.timeline_view, "Timeline"),
            (self.ingest_view, "Ingest status"),
            (self.ledger_view, "Usage"),
            (self.references_view, "Sources and ontology"),
            (self.backup_dialog, "Backup"),
        ):
            action = navigation.addAction(title)
            action.triggered.connect(
                lambda checked=False, page=view: self.stack.setCurrentWidget(page)
            )
        temporal_bar = QToolBar("Time filters", self)
        self.valid_from_edit = QLineEdit(self)
        self.valid_to_edit = QLineEdit(self)
        self.belief_edit = QLineEdit(self)
        for label, edit in (
            ("Valid from", self.valid_from_edit),
            ("Valid through", self.valid_to_edit),
            ("Known as of", self.belief_edit),
        ):
            temporal_bar.addWidget(QLabel(label, self))
            edit.setPlaceholderText("ISO date/instant; blank = all")
            temporal_bar.addWidget(edit)
        apply_time = QPushButton("Apply time", self)
        apply_time.clicked.connect(self._apply_time)
        temporal_bar.addWidget(apply_time)
        self.addToolBar(Qt.ToolBarArea.BottomToolBarArea, temporal_bar)
        self.statusBar().showMessage("Ready; connecting to API…")
        self.setCentralWidget(self.stack)

        # result bundles flow into the viz views; expansion goes through the
        # API client (the view itself never fetches — FR-DC-040)
        for viz in (self.network_view, self.map_view, self.timeline_view):
            state.result_arrived.connect(viz.on_result_arrived)
        self.network_view.bridge.expand_requested.connect(self._expand_neighbors)

        state.connection_changed.connect(self._on_connection_changed)
        # FR-DC-022: fetch the ontology at connect/profile change so the
        # entity view's neighbors relation filter is populated (§2.3)
        self.banner.checked.connect(self._connection_checked)
        self._profile = profile_store.active() if profile_store else None
        if self._profile is not None:
            self.banner._profile_label.setText(f"{self._profile.name} {self._profile.base_url}")
        QTimer.singleShot(0, self.banner.refresh_async)
        # FR-DC-010/022: a selection (search hit, neighbor click) fetches the
        # entity, publishes the EntityDetail bundle, and shows the entity page
        state.selection_changed.connect(self._on_selection_changed)

    def _expand_neighbors(self, entity_id: str) -> None:
        try:
            graph = self.banner.client_factory().entity_neighbors(entity_id)
        except (ApiError, ApiUnreachable):
            self.statusBar().showMessage("Neighbor expansion unavailable; check API connection.")
            return
        self.network_view.push_payload(self.network_view.apply_neighbors(entity_id, graph))

    def _current_query(self) -> tuple[str, str]:
        """The (surface, query text) of the active query surface, for saving."""
        current = self.stack.currentWidget()
        if current not in (self.cypher_console, self.nlq_view):
            current = self._query_source
        if current is self.cypher_console:
            return "cypher", self.cypher_console.editor.toPlainText()
        if current is self.nlq_view:
            return "nlq", self.nlq_view.cypher_edit.toPlainText()
        return "", ""

    def refresh_banner(self) -> None:
        self.banner.refresh()

    def _remember_query_surface(self, index: int) -> None:
        current = self.stack.widget(index)
        if current in (self.cypher_console, self.nlq_view):
            self._query_source = current

    def _on_connection_changed(self, profile: object) -> None:
        if isinstance(profile, ConnectionProfile):
            self.banner._profile_label.setText(f"{profile.name} {profile.base_url}")
        else:
            self.banner._profile_label.setText("disconnected")
        # the client factory rebinds to the new profile's base_url before this
        # handler runs (connection order in __main__); probe the new endpoint now
        self._profile = profile if isinstance(profile, ConnectionProfile) else None
        self.backup_dialog.set_available(
            self._profile or ConnectionProfile(name="current"), False
        )
        self.banner._generation += 1  # discard an old profile's in-flight response
        self.banner.refresh_async()

    def _connection_checked(self, result: dict[str, Any]) -> None:
        if self.banner.is_unreachable():
            self.statusBar().showMessage(
                "API unavailable or degraded; previously loaded results may be stale. "
                "Retrying connection."
            )
        elif self.statusBar().currentMessage().startswith(("API unavailable", "Ready; connecting")):
            self.statusBar().showMessage("API connected.")
        if isinstance(result.get("ontology"), dict):
            self.entity_view.set_ontology(result["ontology"])
        self.backup_dialog.set_available(
            self._profile or ConnectionProfile(name="current"),
            self.banner.status_text() == "ok" and bool(result.get("backup")),
        )

    def _on_selection_changed(self, entity_id: object) -> None:
        if not isinstance(entity_id, str) or not entity_id:
            return
        try:
            detail = self.banner.client_factory().entity(entity_id)
        except (ApiError, ApiUnreachable):
            self.statusBar().showMessage(
                "Entity unavailable; displayed results are from the previous request."
            )
            return
        self.news_view.selected_relation = None
        self.entity_view.show_assertions([])
        self.entity_view._neighbor_rows = []
        self.entity_view.neighbors_model.set_rows([])
        self.entity_view.neighbors_table.setRowCount(0)
        try:
            neighbors = self.banner.client_factory().entity_neighbors(entity_id)
        except (ApiError, ApiUnreachable):
            pass  # Keep the selected entity usable while relation evidence is unavailable.
        else:
            self.entity_view.show_neighbors(neighbors)
            self.entity_view.show_assertions(neighbors.neighbors)
        self._state.publish(QueryOutcomeBundle(result=detail, coverage=None, source="selection"))
        self.stack.setCurrentWidget(self.entity_view)

    def _run_search(self, query: str) -> None:
        try:
            hits = self.banner.client_factory().search(query)
        except (ApiError, ApiUnreachable):
            self.statusBar().showMessage("Search unavailable; check API connection.")
            self.search_bar._model.set_hits([])
            return
        self.statusBar().clearMessage()
        self._state.publish(QueryOutcomeBundle(result=hits, coverage=None, source="search"))

    def _apply_time(self) -> None:
        from limes_desktop.views.viz.bridge import _instant

        values = [
            edit.text().strip()
            for edit in (self.valid_from_edit, self.valid_to_edit, self.belief_edit)
        ]
        if any(value and _instant(value) is None for value in values):
            self.statusBar().showMessage("Use ISO dates or instants for time filters.")
            return
        lower, upper = _instant(values[0]), _instant(values[1], end_of_day=True)
        if lower is not None and upper is not None and lower > upper:
            self.statusBar().showMessage("Validity start must precede its end.")
            return
        self._state.set_temporal_filter(TemporalFilter(*(value or None for value in values)))
        self.statusBar().showMessage("Time filters applied; missing timestamps remain unknown.")
