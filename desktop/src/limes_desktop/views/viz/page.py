# desktop/src/limes_desktop/views/viz/page.py | v0.1.1 | lazy page and ordered profile lifetime
"""This module is imported ONLY when a viz view is instantiated — never from
`bridge.py` at module import time — so the unit suite stays headless-safe."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QShowEvent
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QVBoxLayout, QWidget

from limes_desktop.state import QueryOutcomeBundle, SessionState
from limes_desktop.views.viz.bridge import VizBridge

WEB_DIR = Path(__file__).resolve().parent.parent.parent / "resources" / "web"


class VizPage(QWidget):
    """Base for the three viz views: local HTML + QWebChannel bridge.

    Both the WebEngine view and page are created on first `show()`
    (NFR-DC-071); hidden views never acquire a default profile or page.
    """

    def __init__(
        self, html_name: str, state: SessionState, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._html_name = html_name
        self._state = state
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._view: QWebEngineView | None = None
        self._page: QWebEnginePage | None = None
        self._channel: QWebChannel | None = None
        self._pending_payload: str | None = None
        self._loaded = False
        self.bridge = VizBridge()
        self.bridge.set_state(state)

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802 (Qt naming)
        if self._page is None:
            self._view = QWebEngineView(self)
            # An off-the-record profile belongs to this page, not the global
            # default profile. QObject destroys child objects after the page's
            # WebEngine destructor, so the profile outlives its only page.
            profile = QWebEngineProfile()
            self._page = QWebEnginePage(profile, self._view)
            profile.setParent(self._page)
            self._channel = QWebChannel(self._page)
            self._channel.registerObject("bridge", self.bridge)
            self._page.setWebChannel(self._channel)
            self._view.setPage(self._page)
            self._layout.addWidget(self._view)
            self._page.loadFinished.connect(self._on_load_finished)
            html = (WEB_DIR / self._html_name).read_text(encoding="utf-8")
            base = QUrl.fromLocalFile(str(WEB_DIR / self._html_name))
            self._page.setHtml(html, base)
        super().showEvent(event)

    def push_payload(self, payload_json: str) -> None:
        """Keep hidden views lazy and send the latest result once HTML is ready."""
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

    def on_result_arrived(self, bundle: QueryOutcomeBundle) -> None:
        self.push_payload(self.serialize(bundle))

    def serialize(self, bundle: QueryOutcomeBundle) -> str:
        """Overridden by each view (network/map/timeline payload shaping)."""
        return self.bridge.push_result(bundle)

    @staticmethod
    def resource_dir() -> Path:
        return WEB_DIR
