# desktop/src/limes_desktop/views/viz/timeline.py | v0.1.0 | Plotly bitemporal timeline (FR-DC-042)
from __future__ import annotations

from PySide6.QtWidgets import QWidget

from limes_desktop.state import QueryOutcomeBundle, SessionState
from limes_desktop.views.viz.bridge import timeline_payload
from limes_desktop.views.viz.page import VizPage

__all__ = ["TimelineView"]


class TimelineView(VizPage):
    """Plotly scatter traces over validity time with a belief-time series.

    The page's JS publishes the chosen range through the bridge's
    `on_temporal_range` slot, which sets the shared temporal filter
    (FR-DC-042); every view honors it (FR-DC-043).
    """

    def __init__(self, state: SessionState, parent: QWidget | None = None) -> None:
        super().__init__("timeline.html", state, parent)

    def serialize(self, bundle: QueryOutcomeBundle) -> str:
        return timeline_payload(bundle)
