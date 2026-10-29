# desktop/src/limes_desktop/views/entity.py | v0.1.0 | FR-DC-020/021/022, AC-DC-2: entity view
"""Entity view: bitemporal property table, assertions with provenance
expanders, and an ontology-driven neighborhood table (FR-DC-020/021/022).

The view holds no ontology literals: the relation filter combo is populated
from a canned/pushed `GET /ontology` payload, and re-centering goes through
`SessionState.set_selection`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import (
    QAbstractListModel,
    QModelIndex,
    QPersistentModelIndex,
    Qt,
    Signal,
)
from PySide6.QtWidgets import (
    QComboBox,
    QLabel,
    QListView,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from limes_desktop.api.models import (
    EntityDetail,
    NeighborRow,
)
from limes_desktop.state import QueryOutcomeBundle, SessionState

_VALIDITY_PROPERTIES = ("valid_from", "valid_to")
_BELIEF_PROPERTIES = ("recorded_at",)
_PROPERTY_LABEL = {
    "valid_from": "VALIDITY",
    "valid_to": "VALIDITY (to)",
    "recorded_at": "BELIEF",
}
_PROVENANCE_HEADING = "Provenance"
_SOURCE_LABEL = "source"
_SENTENCE_LABEL = "source sentence"


class _AssertionListModel(QAbstractListModel):
    """FR-DC-021: one row per assertion (edge), with a confidence badge."""

    def __init__(self, parent: QObjectParent | None = None) -> None:
        super().__init__(parent)
        self._rows: list[NeighborRow] = []

    def set_rows(self, rows: list[NeighborRow]) -> None:
        self.beginResetModel()
        self._rows = list(rows)
        self.endResetModel()

    def row_at(self, row: int) -> NeighborRow | None:
        if 0 <= row < len(self._rows):
            return self._rows[row]
        return None

    def rowCount(
        self,
        parent: QModelIndex | QPersistentModelIndex | None = None,
    ) -> int:  # noqa: N802
        if parent is not None and isinstance(parent, QModelIndex) and parent.isValid():
            return 0
        return len(self._rows)

    def data(
        self,
        index: QModelIndex | QPersistentModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> object:
        if role != Qt.ItemDataRole.DisplayRole or not (0 <= index.row() < len(self._rows)):
            return None
        row = self._rows[index.row()]
        confidence = "n/a" if row.edge.confidence is None else f"{row.edge.confidence:.2f}"
        return f"{row.edge.relation} → {row.neighbor.label}  [confidence {confidence}]"


# QObject lives in QtCore; alias keeps the annotation simple for mypy strict
QObjectParent = Any


class EntityView(QWidget):
    """The entity inspector tab of the shared result surface."""

    # re-centering signal (FR-DC-022): neighbor click → set_selection
    neighbor_selected = Signal(str)
    assertion_selected = Signal(str)

    def __init__(
        self,
        state: SessionState,
        client_factory: Callable[[], Any] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._state = state
        self._client_factory = client_factory
        self._ontology: dict[str, Any] | None = None
        self._neighbor_rows: list[NeighborRow] = []

        self.property_table = QTableWidget(0, 2, self)
        self.property_table.setHorizontalHeaderLabels(["property", "value"])
        self.property_table.horizontalHeader().setStretchLastSection(True)

        self.assertion_model = _AssertionListModel(self)
        self.assertion_list = QListView(self)
        self.assertion_list.setModel(self.assertion_model)
        self.assertion_list.clicked.connect(self._on_assertion_clicked)

        self.provenance_box = QTextEdit(self)
        self.provenance_box.setReadOnly(True)
        self.provenance_box.setVisible(False)

        self.relation_filter = QComboBox(self)
        self.relation_filter.currentIndexChanged.connect(self._apply_relation_filter)
        self.neighbors_model = _AssertionListModel(self)  # rows reused for the table
        self.neighbors_table = QTableWidget(0, 3, self)
        self.neighbors_table.setHorizontalHeaderLabels(["relation", "neighbor", "type"])
        self.neighbors_table.horizontalHeader().setStretchLastSection(True)
        self.neighbors_table.clicked.connect(self._on_neighbor_clicked)

        tabs = QTabWidget(self)
        properties_tab = QWidget(self)
        props_layout = QVBoxLayout(properties_tab)
        props_layout.addWidget(self.property_table)
        assertions_tab = QWidget(self)
        assertions_layout = QVBoxLayout(assertions_tab)
        assertions_layout.addWidget(self.assertion_list)
        assertions_layout.addWidget(QLabel(_PROVENANCE_HEADING, self))
        assertions_layout.addWidget(self.provenance_box)
        neighbors_tab = QWidget(self)
        neighbors_layout = QVBoxLayout(neighbors_tab)
        neighbors_layout.addWidget(self.relation_filter)
        neighbors_layout.addWidget(self.neighbors_table)
        tabs.addTab(properties_tab, "Properties")
        tabs.addTab(assertions_tab, "Assertions")
        tabs.addTab(neighbors_tab, "Neighbors")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(tabs)

        state.result_arrived.connect(self._on_result)

    # -- ontology data (no literals; tests inject the canned payload) ----------

    def set_ontology(self, ontology: dict[str, Any]) -> None:
        """Accept the `GET /ontology` payload; populates the filter combo."""
        self._ontology = ontology
        self.relation_filter.blockSignals(True)
        self.relation_filter.clear()
        self.relation_filter.addItem("(all relations)")
        for relation in ontology.get("relation_types") or []:
            name = relation.get("name") if isinstance(relation, dict) else relation
            if name:
                self.relation_filter.addItem(str(name))
        self.relation_filter.blockSignals(False)

    # -- entity rendering (FR-DC-020 / AC-DC-2) ----------------------------------

    def show_entity(self, detail: EntityDetail) -> None:
        entity = detail.entity
        rows: list[tuple[str, str]] = []
        for name in sorted(entity.properties):
            value = entity.properties[name]
            if name in _PROPERTY_LABEL:
                label = _PROPERTY_LABEL[name]
            else:
                label = name
            rendered = value if isinstance(value, str) else str(value)
            if name in _VALIDITY_PROPERTIES or name in _BELIEF_PROPERTIES:
                rendered = f"{label}: {rendered}"
            rows.append((label, rendered))
        self.property_table.setRowCount(len(rows))
        for row, (label, value) in enumerate(rows):
            self.property_table.setItem(row, 0, QTableWidgetItem(label))
            self.property_table.setItem(row, 1, QTableWidgetItem(value))

    # -- assertions (FR-DC-021) ----------------------------------------------------

    def show_assertions(self, rows: list[NeighborRow]) -> None:
        self.assertion_model.set_rows(rows)
        self.provenance_box.setVisible(False)

    def _on_assertion_clicked(self, index: QModelIndex) -> None:
        row = self.assertion_model.row_at(index.row())
        if row is None:
            return
        if row.edge.assertion_id:
            self.assertion_selected.emit(row.edge.assertion_id)
        self._render_provenance(row)
        self.provenance_box.setVisible(True)

    def _render_provenance(self, row: NeighborRow) -> None:
        edge = row.edge
        lines = [
            f"{_SOURCE_LABEL}: {edge.source_id or 'unknown'}",
            f"confidence: {edge.confidence if edge.confidence is not None else 'n/a'}",
            f"assertion id: {edge.assertion_id or 'n/a'}",
            f"validity: {edge.valid_from or '?'} → {edge.valid_to or 'open'}",
            f"belief (recorded at): {edge.recorded_at or '?'}",
            f"evidence document: {edge.evidence_document_id or 'none'}",
        ]
        sentence = self._originating_sentence(edge)
        if sentence is not None:
            lines.append(f"{_SENTENCE_LABEL}: “{sentence}”")
        elif edge.evidence_document_id:
            lines.append(f"{_SENTENCE_LABEL}: unavailable (document not reachable)")
        self.provenance_box.setPlainText("\n".join(lines))

    def _originating_sentence(self, edge: Any) -> str | None:
        """The evidence span of the evidence document's body, when reachable."""
        document_id = getattr(edge, "evidence_document_id", None)
        if not document_id or self._client_factory is None:
            return None
        start, end = edge.evidence_start, edge.evidence_end
        if not isinstance(start, int) or not isinstance(end, int):
            return None
        try:
            document = self._client_factory().entity(str(document_id))
        except Exception:
            return None
        body = (document.get("entity") or {}).get("properties", {}).get("body")
        if not body or not isinstance(body, str):
            return None
        return body[start:end]

    def provenance_text(self) -> str:
        return self.provenance_box.toPlainText()

    # -- neighbors (FR-DC-022) -------------------------------------------------------

    def show_neighbors(self, payload: Any) -> None:
        self._neighbor_rows = list(payload.neighbors)
        self.neighbors_model.set_rows(self._neighbor_rows)
        self._fill_neighbors_table(self._neighbor_rows)

    def _fill_neighbors_table(self, rows: list[NeighborRow]) -> None:
        self.neighbors_table.setRowCount(len(rows))
        for row, item in enumerate(rows):
            self.neighbors_table.setItem(row, 0, QTableWidgetItem(item.edge.relation))
            self.neighbors_table.setItem(row, 1, QTableWidgetItem(item.neighbor.label))
            self.neighbors_table.setItem(row, 2, QTableWidgetItem(item.neighbor.type))

    def _apply_relation_filter(self) -> None:
        selected = self.relation_filter.currentText()
        if not self._neighbor_rows:
            return
        if selected == "(all relations)":
            self._fill_neighbors_table(self._neighbor_rows)
        else:
            self._fill_neighbors_table(
                [r for r in self._neighbor_rows if r.edge.relation == selected]
            )

    def _on_neighbor_clicked(self, index: QModelIndex) -> None:
        rows = self._visible_neighbor_rows()
        if 0 <= index.row() < len(rows):
            neighbor = rows[index.row()].neighbor
            self.neighbor_selected.emit(neighbor.entity_id)
            self._state.set_selection(neighbor.entity_id)

    def _visible_neighbor_rows(self) -> list[NeighborRow]:
        selected = self.relation_filter.currentText()
        if selected == "(all relations)":
            return self._neighbor_rows
        return [r for r in self._neighbor_rows if r.edge.relation == selected]

    # -- SessionState wiring --------------------------------------------------------

    def _on_result(self, bundle: QueryOutcomeBundle) -> None:
        result = bundle.result
        if isinstance(result, EntityDetail):
            self.show_entity(result)
