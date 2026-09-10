# desktop/src/limes_desktop/views/ops/references.py | v0.1.0 | FR-DC-052: references
"""References view (FR-DC-052): the source registry, the ontology type
catalog (relations with domain/range, entity types with supertype), and the
ontology version list — every cell rendered from the API response as DATA.
The module holds no ontology literals (AC-DC-4 guard). Read-only; connection
failures degrade to an inline error pane (AC-DC-6).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QLabel,
    QListWidget,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from limes_desktop.api.errors import ApiError, ApiUnreachable

_SOURCE_COLUMNS = ["source id", "name", "kind", "trust", "backfill", "incremental", "last run"]
_RELATION_COLUMNS = ["relation", "domain", "range", "temporal"]
_ENTITY_COLUMNS = ["entity type", "supertype", "identifying keys"]


class ReferencesView(QWidget):
    """Source registry + ontology catalog + versions, all from API data."""

    def __init__(
        self,
        client_factory: Callable[[], Any],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._client_factory = client_factory

        self.sources_table = self._table(len(_SOURCE_COLUMNS))
        self.relations_table = self._table(len(_RELATION_COLUMNS))
        self.entity_types_table = self._table(len(_ENTITY_COLUMNS))
        self.versions_list = QListWidget(self)

        self.error_pane = QLabel("", self)
        self.error_pane.setWordWrap(True)
        self.error_pane.setStyleSheet("color: #c62828;")
        self.error_pane.setVisible(False)

        self.sources_table.setHorizontalHeaderLabels(_SOURCE_COLUMNS)
        self.relations_table.setHorizontalHeaderLabels(_RELATION_COLUMNS)
        self.entity_types_table.setHorizontalHeaderLabels(_ENTITY_COLUMNS)

        layout = QVBoxLayout(self)
        layout.addWidget(self.error_pane)
        splitter = QSplitter(Qt.Orientation.Vertical, self)
        for label, widget in [
            ("Sources", self.sources_table),
            ("Relations (domain → range)", self.relations_table),
            ("Entity types", self.entity_types_table),
            ("Ontology versions", self.versions_list),
        ]:
            container = QWidget()
            box = QVBoxLayout(container)
            box.addWidget(QLabel(label, container))
            box.addWidget(widget)
            splitter.addWidget(container)
        layout.addWidget(splitter)

    @staticmethod
    def _table(columns: int) -> QTableWidget:
        table = QTableWidget(0, columns)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        return table

    # -- seams for tests ------------------------------------------------------

    def error_text(self) -> str:
        return self.error_pane.text()

    # -- behavior ---------------------------------------------------------------

    def refresh_references(self) -> None:
        """Fetch sources, ontology, and versions; degrade on any failure."""
        client = self._client_factory()
        try:
            sources = client.sources()
            ontology = client.ontology()
            versions = client.ontology_versions()
        except (ApiError, ApiUnreachable) as exc:
            self._show_error(getattr(exc, "detail", str(exc)))
            return
        self._show_error(None)
        self.set_sources(sources)
        self.set_ontology(ontology)
        self.set_versions(versions)

    def set_sources(self, sources: list[Any]) -> None:
        self.sources_table.setRowCount(len(sources))
        for row, s in enumerate(sources):
            cells = [
                s.source_id,
                s.name,
                s.kind,
                f"{s.trust_rank:.2f}",
                "yes" if s.supports_backfill else "no",
                "yes" if s.supports_incremental else "no",
                s.last_run_id or "",
            ]
            for col, text in enumerate(cells):
                self.sources_table.setItem(row, col, QTableWidgetItem(text))

    def set_ontology(self, ontology: dict[str, Any]) -> None:
        relations = ontology.get("relation_types") or {}
        self.relations_table.setRowCount(len(relations))
        for row, spec in enumerate(relations.values()):
            cells = [
                str(spec.get("name", "")),
                ", ".join(spec.get("domain") or []),
                ", ".join(spec.get("range") or []),
                "yes" if spec.get("temporal") else "no",
            ]
            for col, text in enumerate(cells):
                self.relations_table.setItem(row, col, QTableWidgetItem(text))

        entity_types = ontology.get("entity_types") or {}
        self.entity_types_table.setRowCount(len(entity_types))
        for row, spec in enumerate(entity_types.values()):
            cells = [
                str(spec.get("name", "")),
                str(spec.get("supertype") or ""),
                ", ".join(spec.get("identifying_keys") or []),
            ]
            for col, text in enumerate(cells):
                self.entity_types_table.setItem(row, col, QTableWidgetItem(text))

    def set_versions(self, versions: list[str]) -> None:
        self.versions_list.clear()
        for version in versions:
            self.versions_list.addItem(version)

    def _show_error(self, detail: str | None) -> None:
        if detail is None:
            self.error_pane.setVisible(False)
            self.error_pane.setText("")
        else:
            self.error_pane.setText(detail)
            self.error_pane.setVisible(True)

    def showEvent(self, event: Any) -> None:  # noqa: N802 (Qt naming)
        super().showEvent(event)
        self.refresh_references()
