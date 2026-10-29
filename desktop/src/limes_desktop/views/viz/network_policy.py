"""Web visualizations use bundled assets only; HTTP belongs to ApiClient."""

from pathlib import Path

from PySide6.QtCore import QObject, QUrl
from PySide6.QtWebEngineCore import QWebEngineUrlRequestInfo, QWebEngineUrlRequestInterceptor


class LocalResourcesOnly(QWebEngineUrlRequestInterceptor):
    def __init__(self, resource_dir: Path, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.root = resource_dir.resolve()
        self.blocked_urls: list[str] = []

    def allows(self, url: QUrl) -> bool:
        if url.scheme() == "file":
            path = Path(url.toLocalFile()).resolve()
            return path.is_relative_to(self.root) and path.is_file()
        return url.toString() in {"about:blank", "qrc:///qtwebchannel/qwebchannel.js"}

    def interceptRequest(self, info: QWebEngineUrlRequestInfo) -> None:  # noqa: N802
        if not self.allows(info.requestUrl()):
            # Bounded diagnostics without query strings, credentials or fragments.
            url = info.requestUrl()
            self.blocked_urls.append(f"{url.scheme()}://{url.host()}{url.path()}")
            del self.blocked_urls[:-50]
            info.block(True)
