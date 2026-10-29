"""Investigation tracking and qualified evidence; all acquisition stays on the server."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict
from typing import Any
from uuid import uuid4

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class _Signals(QObject):
    done = Signal(object)
    failed = Signal(str)


class _Call(QRunnable):
    def __init__(self, call: Callable[[], Any]) -> None:
        super().__init__()
        self.call = call
        self.signals = _Signals()

    def run(self) -> None:
        try:
            self.signals.done.emit(self.call())
        except Exception as exc:
            self.signals.failed.emit(str(exc))


class NewsView(QWidget):
    def __init__(self, client_factory: Callable[[], Any], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.client_factory = client_factory
        self.selected_entity: str | None = None
        self.selected_relation: str | None = None
        self.investigations: list[dict[str, Any]] = []
        self.claims: list[dict[str, Any]] = []
        self._calls: list[_Call] = []
        self._claim_request = 0
        self._evidence_request = 0
        from limes_desktop.views.developments import DevelopmentPanel

        self.developments = DevelopmentPanel(client_factory, self.call, self)
        self.title = QLineEdit(self)
        self.title.setPlaceholderText("Investigation title")
        self.selector = QComboBox(self)
        self.status = QLabel("Select an entity or assertion to start tracking news.", self)
        self.refresh_button = QPushButton("Refresh investigations", self)
        self.track_button = QPushButton("Track selected entity", self)
        self.relation_button = QPushButton("Track selected relation", self)
        self.pause_button = QPushButton("Pause / resume investigation", self)
        self.replay_button = QPushButton("Replay failed acquisition", self)
        self.list = QListWidget(self)
        self.evidence = QTextEdit(self)
        self.evidence.setReadOnly(True)
        self.include_replaced = QCheckBox("Include replaced claims", self)
        self.include_replaced.stateChanged.connect(self.load_claims)
        self.modality = QComboBox(self)
        self.modality.addItems(
            ["All claims", "asserted", "reported", "denied", "proposed", "conditional", "unknown"]
        )
        layout = QVBoxLayout(self)
        for shared_widget in (self.title, self.selector, self.status):
            layout.addWidget(shared_widget)
        reports = QWidget(self)
        report_layout = QVBoxLayout(reports)
        for widget in (
            self.refresh_button,
            self.track_button,
            self.relation_button,
            self.pause_button,
            self.replay_button,
            self.modality,
            self.include_replaced,
            self.list,
            self.evidence,
        ):
            report_layout.addWidget(widget)
        self.tabs = QTabWidget(self)
        self.tabs.addTab(reports, "Tracking and reports")
        self.tabs.addTab(self.developments, "Cross-source developments")
        layout.addWidget(self.tabs)
        self.refresh_button.clicked.connect(self.refresh)
        self.track_button.clicked.connect(lambda: self.track(False))
        self.relation_button.clicked.connect(lambda: self.track(True))
        self.pause_button.clicked.connect(self.pause)
        self.replay_button.clicked.connect(self.replay)
        self.selector.currentIndexChanged.connect(self.load_claims)
        self.modality.currentIndexChanged.connect(self.load_claims)
        self.list.currentRowChanged.connect(self.show_claim)

    def call(self, action: Callable[[], Any], done: Callable[[Any], None]) -> None:
        task = _Call(action)
        self._calls.append(task)

        def complete(value: Any) -> None:
            done(value)
            self._calls.remove(task)

        def failed(message: str) -> None:
            self.status.setText(
                f"Unavailable: {message}. Tracking changes need an operator session."
            )
            self._calls.remove(task)

        task.signals.done.connect(complete)
        task.signals.failed.connect(failed)
        QThreadPool.globalInstance().start(task)

    def refresh(self) -> None:
        self.call(lambda: self.client_factory().news_investigations(), self.render_investigations)

    def render_investigations(self, rows: list[dict[str, Any]]) -> None:
        rows = [row if isinstance(row, dict) else asdict(row) for row in rows]
        selected = self.selector.currentData()
        self.investigations = rows
        self.selector.blockSignals(True)
        self.selector.clear()
        self.selector.addItem("New investigation", None)
        for row in rows:
            self.selector.addItem(f"{row['title']} — {row['status']}", row["investigation_id"])
        found = self.selector.findData(selected) if selected else -1
        self.selector.setCurrentIndex(found if found >= 0 else (1 if rows else 0))
        self.selector.blockSignals(False)
        self.load_claims()

    def current(self) -> dict[str, Any] | None:
        key = self.selector.currentData()
        return next((r for r in self.investigations if r["investigation_id"] == key), None)

    def track(self, relation: bool) -> None:
        target = self.selected_relation if relation else self.selected_entity
        if not target:
            self.status.setText("Select an assertion or entity first.")
            return
        old = self.current()
        payload = self.request(old)
        field = "assertion_ids" if relation else "entity_ids"
        payload[field] = list(dict.fromkeys([*payload[field], target]))
        self.call(lambda: self.client_factory().track_news(payload), lambda _: self.refresh())

    def request(self, old: dict[str, Any] | None) -> dict[str, Any]:
        return {
            "investigation_id": old["investigation_id"] if old else uuid4().hex,
            "title": (old["title"] if old else self.title.text().strip()) or "Investigation",
            "entity_ids": list(old["entity_ids"]) if old else [],
            "assertion_ids": list(old["assertion_ids"]) if old else [],
            "active": old["active"] if old else True,
            "interval_minutes": old["interval_minutes"] if old else 60,
        }

    def pause(self) -> None:
        old = self.current()
        if old:
            payload = self.request(old)
            payload["active"] = not old["active"]
            self.call(lambda: self.client_factory().track_news(payload), lambda _: self.refresh())

    def replay(self) -> None:
        old = self.current()
        if old:
            self.call(
                lambda: self.client_factory().replay_news(old["investigation_id"]),
                lambda _: self.refresh(),
            )

    def load_claims(self, *_: object) -> None:
        self._claim_request += 1
        request_id = self._claim_request
        old = self.current()
        self.developments.set_case(old["investigation_id"] if old else None)
        if old:
            filters: dict[str, Any] = {
                "investigation_id": old["investigation_id"],
                "include_retracted": self.include_replaced.isChecked(),
            }
            if self.modality.currentIndex() > 0:
                filters["modality"] = self.modality.currentText()
            self.status.setText(
                f"{old['status']}; last successful acquisition: {old.get('last_success') or 'none'}"
            )

            def render_if_current(rows: Any) -> None:
                if (
                    self.selector.currentData() == old["investigation_id"]
                    and request_id == self._claim_request
                ):
                    self.render_claims(rows)

            self.call(lambda: self.client_factory().news_claims(**filters), render_if_current)
        else:
            self.render_claims([])

    def render_claims(self, rows: list[dict[str, Any]]) -> None:
        self._evidence_request += 1
        rows = [row if isinstance(row, dict) else asdict(row) for row in rows]
        self.claims = rows
        self.list.clear()
        self.evidence.clear()
        if not rows:
            self.evidence.setPlainText(
                "No matching claims. Check acquisition status and "
                "supplied text coverage; an empty feed proves no absence."
            )
        for row in rows:
            self.list.addItem(
                f"{row.get('modality', 'unknown')}: {row.get('subject_label', '?')} "
                f"{row['relation']} {row.get('object_label', '?')} — "
                f"{row.get('event_status', 'unknown')}"
            )

    def show_claim(self, index: int) -> None:
        if not 0 <= index < len(self.claims):
            return
        self._evidence_request += 1
        request_id = self._evidence_request
        claim = self.claims[index]
        fields = (
            "modality",
            "attribution",
            "assessment",
            "event_status",
            "time_precision",
            "event_candidate",
            "source_trust",
            "confidence",
            "publisher",
            "dispatch_id",
            "syndication_key",
            "valid_from",
            "valid_to",
            "recorded_at",
            "retracted_at",
            "report_url",
        )
        lines = [f"{name.replace('_', ' ')}: {claim.get(name) or 'unknown'}" for name in fields]
        lines.append("Extraction confidence, source trust and corroboration are separate.")
        lines.append("Event matching is unresolved; repeated dispatches are dependent reporting.")
        self.evidence.setPlainText("\n".join(lines))

        def show_document(document: dict[str, Any]) -> None:
            if self.list.currentRow() != index or request_id != self._evidence_request:
                return
            body = document.get("body") or ""
            start, end = claim.get("evidence_start"), claim.get("evidence_end")
            span = body[start:end] if isinstance(start, int) and isinstance(end, int) else "unknown"
            self.evidence.setPlainText(
                "\n".join(lines) + f"\nSource span: {span}\n"
                "Full article text unavailable; evidence is the supplied headline/snippet.\n"
                f"Prior version: {document.get('previous_document_id') or 'none known'}"
            )

        self.call(
            lambda: self.client_factory().news_document(claim["evidence_document_id"]),
            show_document,
        )
