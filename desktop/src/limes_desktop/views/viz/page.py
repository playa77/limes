# desktop/src/limes_desktop/views/viz/page.py | v0.1.1 | lazy page and ordered profile lifetime
"""This module is imported ONLY when a viz view is instantiated — never from
`bridge.py` at module import time — so the unit suite stays headless-safe."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QUrl
from PySide6.QtGui import QShowEvent
from PySide6.QtWebChannel import QWebChannel

if TYPE_CHECKING:
    from PySide6.QtWebEngineCore import QWebEnginePage
    from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QVBoxLayout, QWidget

from limes_desktop.state import QueryOutcomeBundle, SessionState, TemporalFilter
from limes_desktop.views.viz.bridge import VizBridge, temporal_bundle

WEB_DIR = Path(__file__).resolve().parent.parent.parent / "resources" / "web"


class VizPage(QWidget):
    """Base for the three viz views: local HTML + QWebChannel bridge.

    Both the WebEngine view and page are created on first `show()`
    (NFR-DC-071); hidden views never acquire a default profile or page.
    """

    def __init__(self, html_name: str, state: SessionState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._html_name = html_name
        self._state = state
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._view: QWebEngineView | None = None
        self._page: QWebEnginePage | None = None
        self._channel: QWebChannel | None = None
        self._pending_payload: str | None = None
        self._last_payload: str | None = None
        self._loaded = False
        self._last_bundle: QueryOutcomeBundle | None = None
        self._temporal = state.temporal_filter
        self._selected = state.selection
        state.temporal_filter_changed.connect(self._set_temporal)
        state.selection_changed.connect(self._set_selection)
        self.bridge = VizBridge()
        self.bridge.set_state(state)

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802 (Qt naming)
        if self._page is None:
            from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
            from PySide6.QtWebEngineWidgets import QWebEngineView

            from limes_desktop.views.viz.network_policy import LocalResourcesOnly

            self._view = QWebEngineView(self)
            # An off-the-record profile belongs to this page, not the global
            # default profile. QObject destroys child objects after the page's
            # WebEngine destructor, so the profile outlives its only page.
            profile = QWebEngineProfile()
            self._network_guard = LocalResourcesOnly(WEB_DIR, profile)
            profile.setUrlRequestInterceptor(self._network_guard)
            self._page = QWebEnginePage(profile, self._view)
            profile.setParent(self._page)
            self._channel = QWebChannel(self._page)
            self._channel.registerObject("bridge", self.bridge)
            self._page.setWebChannel(self._channel)
            self._view.setPage(self._page)
            self._layout.addWidget(self._view)
            self._page.loadFinished.connect(self._on_load_finished)
            base = QUrl.fromLocalFile(str(WEB_DIR / self._html_name))
            self._page.load(base)
        super().showEvent(event)

    def push_payload(self, payload_json: str) -> None:
        """Keep hidden views lazy and send the latest result once HTML is ready."""
        self._last_payload = payload_json
        self._pending_payload = payload_json
        self._flush_payload()

    def _on_load_finished(self, ok: bool) -> None:
        self._loaded = ok
        self._flush_payload()

    def _flush_payload(self) -> None:
        if self._page is not None and self._loaded and self._pending_payload is not None:
            payload = self._pending_payload
            self._pending_payload = None
            self._page.runJavaScript(f"window.pushResult && window.pushResult({payload});")

    def _set_temporal(self, temporal: TemporalFilter) -> None:
        self._temporal = temporal
        self._redraw()

    def _set_selection(self, value: object) -> None:
        self._selected = str(value) if value else None
        self._redraw()

    def _redraw(self) -> None:
        if self._last_bundle is not None:
            payload = json.loads(self.serialize(temporal_bundle(self._last_bundle, self._temporal)))
            payload["selected_id"] = self._selected
            self.push_payload(json.dumps(payload))

    def on_result_arrived(self, bundle: QueryOutcomeBundle) -> None:
        from limes_desktop.api.models import GraphResult

        if isinstance(bundle.result, GraphResult):
            self._last_bundle = bundle
            self._redraw()

    def serialize(self, bundle: QueryOutcomeBundle) -> str:
        """Overridden by each view (network/map/timeline payload shaping)."""
        return self.bridge.push_result(bundle)

    @staticmethod
    def resource_dir() -> Path:
        return WEB_DIR
