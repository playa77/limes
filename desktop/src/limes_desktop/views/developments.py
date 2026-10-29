"""Cross-source investigation workspace; all evidence and decisions travel via HTTP."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from PySide6.QtCore import Qt
from PySide6.QtGui import QPen
from PySide6.QtWidgets import (
    QComboBox,
    QGraphicsScene,
    QGraphicsView,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class _Unavailable:
    def __init__(self, message: str) -> None:
        self.message = message


class DevelopmentPanel(QWidget):
    def __init__(
        self,
        client_factory: Callable[[], Any],
        call: Callable[[Callable[[], Any], Callable[[Any], None]], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.client_factory, self.call = client_factory, call
        self.key: str | None = None
        self.generation = 0
        self.document_generation = 0
        self.rows: list[dict[str, Any]] = []
        self.candidates: list[dict[str, Any]] = []
        self.status = QLabel("Load cross-source evidence for the selected investigation.", self)
        self.valid = QLineEdit(self)
        self.valid.setPlaceholderText(
            "Valid at (ISO instant with timezone; blank includes history)"
        )
        self.believed = QLineEdit(self)
        self.believed.setPlaceholderText(
            "Known at (ISO instant with timezone; blank includes history)"
        )
        self.load_button = QPushButton("Load cross-source developments", self)
        self.evidence_list = QListWidget(self)
        self.detail = QTextEdit(self)
        self.detail.setReadOnly(True)
        self.scene = QGraphicsScene(self)
        self.network = QGraphicsView(self.scene, self)
        self.map_scene = QGraphicsScene(self)
        self.map_view = QGraphicsView(self.map_scene, self)
        self.timeline = QTableWidget(0, 5, self)
        self.timeline.setHorizontalHeaderLabels(["Axis", "Instant", "Kind", "Evidence", "State"])
        self.timeline.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabs = QTabWidget(self)
        for page, name in (
            (self.evidence_list, "Evidence"),
            (self.network, "Network"),
            (self.map_view, "Map — coordinates only"),
            (self.timeline, "Timeline"),
        ):
            self.tabs.addTab(page, name)
        self.matches = QComboBox(self)
        self.left = QComboBox(self)
        self.right = QComboBox(self)
        self.decision = QComboBox(self)
        self.decision.addItems(["unresolved", "same_event", "different_event"])
        self.assessment = QComboBox(self)
        self.assessment.addItems(["unassessed", "supports", "challenges", "context"])
        self.independence = QComboBox(self)
        self.independence.addItems(["unknown", "dependent", "independent"])
        self.rationale = QLineEdit(self)
        self.rationale.setPlaceholderText("Review rationale (operator session required)")
        self.save_button = QPushButton("Record event-match review", self)
        layout = QVBoxLayout(self)
        for widget in (
            self.status,
            self.valid,
            self.believed,
            self.load_button,
            self.tabs,
            self.detail,
            self.matches,
            self.left,
            self.right,
            self.decision,
            self.assessment,
            self.independence,
            self.rationale,
            self.save_button,
        ):
            layout.addWidget(widget)
        self.load_button.clicked.connect(self.load)
        self.save_button.clicked.connect(self.save)
        self.matches.currentIndexChanged.connect(self.select_candidate)
        self.evidence_list.currentRowChanged.connect(self.show_evidence)
        self.timeline.cellClicked.connect(self.select_time)
        self.scene.selectionChanged.connect(self.select_network)
        self.map_scene.selectionChanged.connect(self.select_map)
        self.valid.textChanged.connect(self.invalidate)
        self.believed.textChanged.connect(self.invalidate)

    def invalidate(self, *_: object) -> None:
        self.generation += 1
        self.document_generation += 1
        self.rows, self.candidates = [], []
        self.scene.clear()
        self.map_scene.clear()
        self.timeline.setRowCount(0)
        self.evidence_list.clear()
        self.matches.clear()
        self.left.clear()
        self.right.clear()
        self.detail.clear()
        self.status.setText("Results cleared; load evidence for the selected targets and times.")

    def set_case(self, key: str | None) -> None:
        self.key = key
        self.invalidate()

    def load(self) -> None:
        if not self.key:
            self.status.setText("Select an investigation first.")
            return
        key = self.key
        self.invalidate()
        generation = self.generation
        filters = {
            k: w.text().strip()
            for k, w in (("as_of", self.valid), ("believed", self.believed))
            if w.text().strip()
        }
        self.status.setText("Loading cross-source evidence…")

        def render_if_current(data: Any) -> None:
            if key == self.key and generation == self.generation:
                self.render_developments(
                    asdict(data) if is_dataclass(data) and not isinstance(data, type) else data
                )

        self.invoke(
            lambda: self.client_factory().news_developments(key, **filters), render_if_current
        )

    def render_developments(self, data: dict[str, Any]) -> None:
        self.rows = data["evidence"]
        self.candidates = data["candidates"]
        self.status.setText("; ".join(data["diagnosis"]) + f" Coverage: {data['coverage']}")
        self.evidence_list.clear()
        self.timeline.setSortingEnabled(False)
        self.timeline.setRowCount(0)
        self.scene.clear()
        self.matches.clear()
        self.left.clear()
        self.right.clear()
        for row in self.rows:
            label = (
                f"{row['kind']}: {row['subject_label']} → {row['relation']} → "
                f"{row['object_label']} ({row['evidence_id']})"
            )
            self.left.addItem(label, row["evidence_id"])
            self.right.addItem(label, row["evidence_id"])
        for candidate in self.candidates:
            self.matches.addItem(
                f"{candidate['decision']} / {candidate['assessment']} / "
                f"{candidate['independence']}: {candidate['left']} ↔ {candidate['right']}",
                candidate,
            )
        self.map_scene.clear()
        self.map_scene.addRect(-360, -180, 720, 360)
        for location in data.get("locations", []):
            x, y = float(location["longitude"]) * 2, -float(location["latitude"]) * 2
            marker = self.map_scene.addEllipse(x - 3, y - 3, 6, 6)
            marker.setFlag(marker.GraphicsItemFlag.ItemIsSelectable)
            marker.setData(0, location["entity_id"])
            marker_label = self.map_scene.addText(
                str(location.get("label") or location["entity_id"])
            )
            marker_label.setPos(x + 4, y)
        if not data.get("locations"):
            self.map_scene.addText("No directly geolocated endpoints. Positions are unknown.")
        self.detail.setPlainText("Review history: " + json.dumps(data["reviews"], indent=2))
        for index, row in enumerate(self.rows):
            p = row["properties"]
            state = p.get("modality") or row["kind"]
            label = f"{row['kind']} / {state}: {row['subject_label']} → {row['relation']} → "
            label += row["object_label"]
            self.evidence_list.addItem(label)
            y = index * 80
            pen = QPen(Qt.GlobalColor.darkBlue)
            if row["kind"] != "assertion":
                pen.setStyle(Qt.PenStyle.DashLine)
            self.scene.addLine(0, y + 25, 700, y + 25, pen)
            text = self.scene.addText(label)
            text.setPos(0, y)
            box = self.scene.addRect(0, y, 700, 55, pen)
            box.setFlag(box.GraphicsItemFlag.ItemIsSelectable)
            box.setData(0, index)
            for field, axis in (("valid_from", "validity"), ("recorded_at", "recorded")):
                instant = p.get(field)
                if (
                    axis == "validity"
                    and row["kind"] == "claim"
                    and p.get("time_precision", "unknown") == "unknown"
                ):
                    continue
                if instant:
                    parsed = datetime.fromisoformat(str(instant).replace("Z", "+00:00"))
                    if parsed.tzinfo is not None:
                        instant = parsed.astimezone(UTC).isoformat()
                    n = self.timeline.rowCount()
                    self.timeline.insertRow(n)
                    for col, value in enumerate(
                        (axis, instant, row["kind"], row["evidence_id"], state)
                    ):
                        item = QTableWidgetItem(str(value))
                        item.setData(Qt.ItemDataRole.UserRole, index)
                        self.timeline.setItem(n, col, item)
        self.timeline.setSortingEnabled(True)
        self.timeline.sortItems(1)
        self.timeline.resizeColumnsToContents()

    def select_time(self, row: int, _: int) -> None:
        item = self.timeline.item(row, 0)
        if item:
            self.evidence_list.setCurrentRow(item.data(Qt.ItemDataRole.UserRole))

    def select_network(self) -> None:
        selected = self.scene.selectedItems()
        if selected and isinstance(selected[0].data(0), int):
            self.evidence_list.setCurrentRow(selected[0].data(0))

    def select_map(self) -> None:
        selected = self.map_scene.selectedItems()
        if selected:
            entity_id = selected[0].data(0)
            index = next(
                (
                    i
                    for i, row in enumerate(self.rows)
                    if entity_id in (row["subject_id"], row["object_id"])
                ),
                -1,
            )
            self.evidence_list.setCurrentRow(index)

    def show_evidence(self, index: int) -> None:
        self.document_generation += 1
        if not 0 <= index < len(self.rows):
            return
        row = self.rows[index]
        generation = self.document_generation
        lines = json.dumps(row, indent=2, ensure_ascii=False)
        lines += "\nChronology implies neither causation nor misconduct."
        self.detail.setPlainText(lines)
        document = row["properties"].get("evidence_document_id")
        if row["kind"] == "claim" and document:

            def show(doc: dict[str, Any]) -> None:
                if generation == self.document_generation:
                    p = row["properties"]
                    start, end = p.get("evidence_start"), p.get("evidence_end")
                    body = doc.get("body") or ""
                    span = (
                        body[start:end]
                        if isinstance(start, int) and isinstance(end, int)
                        else "unknown"
                    )
                    self.detail.setPlainText(lines + f"\nSource span: {span}\n" + json.dumps(doc))

            self.invoke(lambda: self.client_factory().news_document(document), show)
        elif row["kind"] != "claim":

            def show_assertion(data: dict[str, Any]) -> None:
                if generation == self.document_generation:
                    self.detail.setPlainText(
                        lines
                        + "\n"
                        + json.dumps(data, ensure_ascii=False)
                        + "\nArchive preview:\n"
                        + str(data.get("preview") or "unavailable")
                    )

            self.invoke(
                lambda: self.client_factory().assertion_evidence(row["properties"]["assertion_id"]),
                show_assertion,
            )

    def save(self) -> None:
        left, right = self.left.currentData(), self.right.currentData()
        if (
            not left
            or not right
            or left == right
            or not self.key
            or not self.rationale.text().strip()
        ):
            self.status.setText("Select a candidate and provide a review rationale.")
            return
        payload = {
            "request_id": str(uuid4()),
            "left": left,
            "right": right,
            "decision": self.decision.currentText(),
            "assessment": self.assessment.currentText(),
            "independence": self.independence.currentText(),
            "rationale": self.rationale.text().strip(),
        }
        key = self.key
        self.invoke(
            lambda: self.client_factory().review_event_match(key, payload), lambda _: self.load()
        )

    def select_candidate(self, *_: object) -> None:
        candidate = self.matches.currentData()
        if candidate:
            self.left.setCurrentIndex(self.left.findData(candidate["left"]))
            self.right.setCurrentIndex(self.right.findData(candidate["right"]))
            for widget, key in (
                (self.decision, "decision"),
                (self.assessment, "assessment"),
                (self.independence, "independence"),
            ):
                widget.setCurrentText(candidate[key])
            self.rationale.setText(candidate.get("rationale") or "")

    def invoke(self, action: Callable[[], Any], done: Callable[[Any], None]) -> None:
        generation = self.generation

        def guarded() -> Any:
            try:
                return action()
            except Exception as exc:
                return _Unavailable(str(exc))

        def complete(data: Any) -> None:
            if generation != self.generation:
                return
            if isinstance(data, _Unavailable):
                self.status.setText(
                    f"Evidence unavailable: {data.message}. Retry loading explicitly."
                )
            else:
                done(data)

        self.call(guarded, complete)
