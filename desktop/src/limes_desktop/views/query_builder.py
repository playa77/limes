# desktop/src/limes_desktop/views/query_builder.py | v0.1.0 | FR-DC-031 builder
"""Schema-driven query builder (FR-DC-031).

The builder is constructed ENTIRELY from `ApiClient.builder_schema()` — the
GET /builder/schema projection — and holds zero ontology literals: every
combo's options are computed from the schema's domain/range data, with the
exact `relations_for`/`targets_for` semantics of the Dash UI's
`src/limes/ui/components/builder.py` (domain side ⇒ "out", range side ⇒
"in", supertype-expanded concrete types). Start-type combo ← schema
`entity_types`; per-hop relation + direction + target combos ← only the
schema-admissible triples. Submit calls `query_builder(spec)` and publishes
the bundle with the outcome's coverage/diagnosis (Task-7 invariant: never
None silently).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from limes_desktop.api.errors import ApiError, ApiUnreachable
from limes_desktop.state import QueryOutcomeBundle, SessionState

_DIRECTION_LABELS = {"out": "outgoing", "in": "incoming"}


@dataclass
class HopRow:
    """One hop's controls: relation + direction + target, all schema-fed."""

    relation_combo: QComboBox
    direction_combo: QComboBox
    target_combo: QComboBox
    container: QWidget

    def spec(self) -> dict[str, Any]:
        return {
            "relation": self.relation_combo.currentData(),
            "direction": self.direction_combo.currentData(),
            "target_type": self.target_combo.currentData(),
        }


class BuilderView(QWidget):
    """Compose a BuilderSpec from schema-admissible dropdowns only."""

    def __init__(
        self,
        state: SessionState,
        client_factory: Callable[[], Any],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._state = state
        self._client_factory = client_factory
        self._schema: dict[str, Any] | None = None
        self._shown = False

        self.start_type_combo = QComboBox(self)
        self.add_hop_button = QPushButton("Add hop", self)
        self.remove_hop_button = QPushButton("Remove hop", self)
        self.submit_button = QPushButton("Run", self)
        self.error_pane = QLabel("", self)
        self.error_pane.setWordWrap(True)
        self.error_pane.setStyleSheet("color: #c62828;")
        self.error_pane.setVisible(False)

        self._hops_layout = QVBoxLayout()
        self.hop_rows: list[HopRow] = []

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Start type:", self))
        layout.addWidget(self.start_type_combo)
        layout.addLayout(self._hops_layout)
        buttons = QHBoxLayout()
        buttons.addWidget(self.add_hop_button)
        buttons.addWidget(self.remove_hop_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        layout.addWidget(self.submit_button)
        layout.addWidget(self.error_pane)
        layout.addStretch(1)

        self.start_type_combo.currentTextChanged.connect(self._on_start_type_changed)
        self.add_hop_button.clicked.connect(self.add_hop)
        self.remove_hop_button.clicked.connect(self.remove_hop)
        self.submit_button.clicked.connect(self._submit)

    # -- seams for tests ------------------------------------------------------

    def error_text(self) -> str:
        return self.error_pane.text()

    # -- schema population (the only source of options) ------------------------

    def set_schema(self, schema: dict[str, Any]) -> None:
        """Populate every combo from the GET /builder/schema projection."""
        self._schema = schema
        self.start_type_combo.blockSignals(True)
        self.start_type_combo.clear()
        for entry in schema.get("entity_types", []):
            self.start_type_combo.addItem(str(entry["name"]), str(entry["name"]))
        self.start_type_combo.blockSignals(False)
        self._clear_hops()
        self._on_start_type_changed()

    def reload_schema(self) -> None:
        """Fetch the schema from the client; errors surface verbatim."""
        try:
            schema = self._client_factory().builder_schema()
        except (ApiError, ApiUnreachable) as exc:
            self._show_error(getattr(exc, "detail", str(exc)))
            return
        self._show_error(None)
        self.set_schema(schema)

    # -- schema-derived option sets (mirrors ui/components/builder.py) -----------

    def _entity_types(self) -> dict[str, dict[str, Any]]:
        return {str(e["name"]): e for e in (self._schema or {}).get("entity_types", [])}

    def _relation_types(self) -> dict[str, dict[str, Any]]:
        return {str(e["name"]): e for e in (self._schema or {}).get("relation_types", [])}

    def _supertype_chain(self, type_name: str) -> list[str]:
        chain: list[str] = []
        supertypes = {name: entry.get("supertype") for name, entry in self._entity_types().items()}
        current = supertypes.get(type_name)
        while current is not None:
            chain.append(current)
            current = supertypes.get(current)
        return chain

    def _admitted(self, declared: list[str], type_name: str) -> bool:
        if type_name in declared:
            return True
        return any(s in declared for s in self._supertype_chain(type_name))

    def _admitted_types(self, relation: str, side: str) -> list[str]:
        declared = self._relation_types().get(relation, {}).get(side, [])
        concrete = list(self._entity_types())
        admitted: list[str] = []
        for name in declared:
            if name in concrete and name not in admitted:
                admitted.append(name)
            for candidate in concrete:
                if candidate not in admitted and name in self._supertype_chain(candidate):
                    admitted.append(candidate)
        return admitted

    def _directions_for(self, type_name: str, relation: str) -> list[str]:
        spec = self._relation_types().get(relation, {})
        directions: list[str] = []
        if self._admitted(list(spec.get("domain", [])), type_name):
            directions.append("out")
        if self._admitted(list(spec.get("range", [])), type_name):
            directions.append("in")
        return directions

    def _targets_for(self, relation: str, direction: str) -> list[str]:
        side = "range" if direction == "out" else "domain"
        return self._admitted_types(relation, side)

    # -- hop rows ----------------------------------------------------------------

    def _clear_hops(self) -> None:
        for row in self.hop_rows:
            self._hops_layout.removeWidget(row.container)
            row.container.deleteLater()
        self.hop_rows = []

    def add_hop(self) -> None:
        row = self._make_hop_row()
        self._fill_hop(row)

    def remove_hop(self) -> None:
        if len(self.hop_rows) <= 1:
            return
        row = self.hop_rows.pop()
        self._hops_layout.removeWidget(row.container)
        row.container.deleteLater()

    def _make_hop_row(self) -> HopRow:
        container = QWidget(self)
        layout = QHBoxLayout(container)
        relation_combo = QComboBox(container)
        direction_combo = QComboBox(container)
        target_combo = QComboBox(container)
        layout.addWidget(QLabel("relation", container))
        layout.addWidget(relation_combo)
        layout.addWidget(QLabel("direction", container))
        layout.addWidget(direction_combo)
        layout.addWidget(QLabel("target", container))
        layout.addWidget(target_combo)
        row = HopRow(relation_combo, direction_combo, target_combo, container)
        self._hops_layout.addWidget(container)
        self.hop_rows.append(row)

        # downstream-only refresh: refilling the relation combo here would
        # reset the user's selection (it depends only on the current type)
        relation_combo.currentTextChanged.connect(
            lambda _: self._refresh_hop(row, refill_relation=False)
        )
        direction_combo.currentTextChanged.connect(
            lambda _: self._refresh_hop(row, refill_relation=False)
        )
        target_combo.currentTextChanged.connect(lambda _: self._refresh_chain_from(row))
        return row

    def _refresh_chain_from(self, row: HopRow) -> None:
        """A target change re-admissibilizes the next hop's relations."""
        index = self.hop_rows.index(row)
        if index + 1 < len(self.hop_rows):
            self._fill_hop(self.hop_rows[index + 1])

    @staticmethod
    def _refill(combo: QComboBox, values: list[str], labels: dict[str, str] | None = None) -> None:
        previous = combo.currentData()
        combo.blockSignals(True)
        combo.clear()
        for value in values:
            combo.addItem((labels or {}).get(value, value), value)
        index = combo.findData(previous)
        if index >= 0:
            combo.setCurrentIndex(index)
        combo.blockSignals(False)

    def _fill_hop(self, row: HopRow) -> None:
        self._refresh_hop(row)

    def _current_type(self, row: HopRow) -> str:
        index = self.hop_rows.index(row)
        if index == 0:
            current = self.start_type_combo.currentData()
            return str(current) if current else ""
        previous = self.hop_rows[index - 1]
        target = previous.target_combo.currentData()
        return str(target) if target else ""

    def _refresh_hop(self, row: HopRow, refill_relation: bool = True) -> None:
        if refill_relation:
            current_type = self._current_type(row)
            self._refill(
                row.relation_combo,
                [
                    relation
                    for relation in self._relation_types()
                    if self._directions_for(current_type, relation)
                ],
            )
        relation = row.relation_combo.currentData()
        self._refill(
            row.direction_combo,
            self._directions_for(self._current_type(row), str(relation)) if relation else [],
            _DIRECTION_LABELS,
        )
        direction = row.direction_combo.currentData()
        self._refill(
            row.target_combo,
            self._targets_for(str(relation), str(direction)) if relation and direction else [],
        )
        # Signals are blocked during refill; explicitly refresh the whole suffix.
        self._refresh_chain_from(row)

    # -- behavior -----------------------------------------------------------------

    def _on_start_type_changed(self) -> None:
        if self._schema is None:
            return
        # the first hop chains off the start type; deeper hops chain off their
        # predecessor's target, so a start-type change rebuilds from the top
        first = self.hop_rows[0] if self.hop_rows else self._make_hop_row()
        self._fill_hop(first)

    def _spec(self) -> dict[str, Any] | None:
        start = self.start_type_combo.currentData()
        if not start:
            return None
        hops = [row.spec() for row in self.hop_rows]
        if any(not all(h.values()) for h in hops):
            return None
        current = str(start)
        for hop in hops:
            if hop["direction"] not in self._directions_for(current, hop["relation"]) or hop[
                "target_type"
            ] not in self._targets_for(hop["relation"], hop["direction"]):
                return None
            current = hop["target_type"]
        return {"start_type": str(start), "start_filters": {}, "hops": hops}

    def _submit(self) -> None:
        spec = self._spec()
        if spec is None:
            return
        try:
            outcome = self._client_factory().query_builder(spec)
        except (ApiError, ApiUnreachable) as exc:
            self._show_error(getattr(exc, "detail", str(exc)))
            return
        self._show_error(None)
        self._state.publish(
            QueryOutcomeBundle(
                result=outcome.results,
                coverage=outcome.coverage,
                source="builder",
                cypher=outcome.cypher,
                nlq=None,
                diagnosis=outcome.diagnosis,
            )
        )

    def _show_error(self, detail: str | None) -> None:
        if detail is None:
            self.error_pane.setVisible(False)
            self.error_pane.setText("")
        else:
            # verbatim per FR-DC-032 — no rephrasing, no prefix
            self.error_pane.setText(detail)
            self.error_pane.setVisible(True)

    def showEvent(self, event: Any) -> None:  # noqa: N802 (Qt naming)
        """Lazy schema fetch: one fetch on first show, none at construction."""
        super().showEvent(event)
        if not self._shown:
            self._shown = True
            self.reload_schema()
