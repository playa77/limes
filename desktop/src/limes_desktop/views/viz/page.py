# desktop/src/limes_desktop/views/viz/page.py | v0.1.0 | lazy QWebEngine page (NFR-DC-071/072)
"""This module is imported ONLY when a viz view is instantiated — never from
`bridge.py` at module import time — so the unit suite stays headless-safe."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QShowEvent
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEnginePage
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QWidget

from limes_desktop.state import QueryOutcomeBundle, SessionState
from limes_desktop.views.viz.bridge import VizBridge

WEB_DIR = Path(__file__).resolve().parent.parent.parent / "resources" / "web"


class VizPage(QWebEngineView):
    """Base for the three viz views: local HTML + QWebChannel bridge.

    The QWebEnginePage is created lazily on first `show()` (NFR-DC-071);
    constructing the object alone never starts the WebEngine process.
    """

    def __init__(
        self, html_name: str, state: SessionState, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._html_name = html_name
        self._state = state
        self._page: QWebEnginePage | None = None
        self._channel: QWebChannel | None = None
        self.bridge = VizBridge()
        self.bridge.set_state(state)

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802 (Qt naming)
        if self._page is None:
            self._page = QWebEnginePage(self)
            self._channel = QWebChannel(self._page)
            self._channel.registerObject("bridge", self.bridge)
            self._page.setWebChannel(self._channel)
            self.setPage(self._page)
            html = (WEB_DIR / self._html_name).read_text(encoding="utf-8")
            base = QUrl.fromLocalFile(str(WEB_DIR / self._html_name))
            self.setHtml(html, base)
        super().showEvent(event)

    def push_payload(self, payload_json: str) -> None:
        """Deliver a serialized payload to the page's renderer."""
        self.page().runJavaScript(f"window.pushResult && window.pushResult({payload_json});")

    def on_result_arrived(self, bundle: QueryOutcomeBundle) -> None:
        self.push_payload(self.serialize(bundle))

    def serialize(self, bundle: QueryOutcomeBundle) -> str:
        """Overridden by each view (network/map/timeline payload shaping)."""
        return self.bridge.push_result(bundle)

    @staticmethod
    def resource_dir() -> Path:
        return WEB_DIR
