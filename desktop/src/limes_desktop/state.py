# desktop/src/limes_desktop/state.py | v0.1.1 | SessionState signal hub (FR-DC-043/042)
from collections import deque
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal

from limes_desktop.api.models import (
    CoverageReport,
    Diagnosis,
    EntityDetail,
    GraphResult,
    NlqOutcome,
    SearchHit,
)
from limes_desktop.config import ConnectionProfile

__all__ = ["QueryOutcomeBundle", "SessionState", "TemporalFilter"]


@dataclass(frozen=True)
class TemporalFilter:
    """Bitemporal view filter: validity time vs belief time (as-of date)."""

    validity_from: str | None = None
    validity_to: str | None = None
    belief_as_of: str | None = None


@dataclass(frozen=True)
class QueryOutcomeBundle:
    """Immutable query outcome so views cannot cross-mutate shared payloads."""

    result: GraphResult | EntityDetail | list[SearchHit]
    coverage: CoverageReport | None
    source: str
    cypher: str | None = None
    nlq: NlqOutcome | None = None
    diagnosis: Diagnosis | None = None


class SessionState(QObject):
    """Central signal hub connecting views and the API client (FR-DC-043)."""

    selection_changed = Signal(object)  # str | None (entity id)
    result_arrived = Signal(object)  # QueryOutcomeBundle
    connection_changed = Signal(object)  # ConnectionProfile | None
    temporal_filter_changed = Signal(object)  # TemporalFilter

    _HISTORY_MAX = 100

    def __init__(self) -> None:
        super().__init__()
        self.selection: str | None = None
        self.temporal_filter = TemporalFilter()
        self._history: deque[QueryOutcomeBundle] = deque(maxlen=self._HISTORY_MAX)

    def set_selection(self, entity_id: str | None) -> None:
        self.selection = entity_id
        self.selection_changed.emit(entity_id)

    def publish(self, bundle: QueryOutcomeBundle) -> None:
        self._history.append(bundle)
        self.result_arrived.emit(bundle)

    def set_connection(self, profile: ConnectionProfile | None) -> None:
        self.connection_changed.emit(profile)

    def set_temporal_filter(self, f: TemporalFilter) -> None:
        self.temporal_filter = f
        self.temporal_filter_changed.emit(f)

    def history(self) -> list[QueryOutcomeBundle]:
        return list(self._history)
