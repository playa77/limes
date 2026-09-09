# desktop/src/limes_desktop/views/viz/map.py | v0.1.0 | Leaflet map view (FR-DC-041)
from __future__ import annotations

from PySide6.QtWidgets import QWidget

from limes_desktop.state import QueryOutcomeBundle, SessionState, TemporalFilter
from limes_desktop.views.viz.bridge import map_payload
from limes_desktop.views.viz.page import VizPage

__all__ = ["MapView"]


class MapView(VizPage):
    """Point-geometry markers + polylines for the selected entity's geo edges.

    Honors the shared temporal filter (FR-DC-043): the last filter received
    is reapplied to every payload.
    """

    def __init__(self, state: SessionState, parent: QWidget | None = None) -> None:
        super().__init__("map.html", state, parent)
        self._filter = TemporalFilter()
        self._selected_id: str | None = None
        state.temporal_filter_changed.connect(self._on_filter)
        state.selection_changed.connect(self._on_selection)
        self.bridge.selection_changed.connect(self._on_selection)

    def _on_filter(self, f: TemporalFilter) -> None:
        self._filter = f

    def _on_selection(self, entity_id: object) -> None:
        self._selected_id = str(entity_id) if entity_id else None

    def serialize(self, bundle: QueryOutcomeBundle) -> str:
        return map_payload(bundle, selected_id=self._selected_id)
