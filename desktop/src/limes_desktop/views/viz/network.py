# desktop/src/limes_desktop/views/viz/network.py | v0.1.0 | Cytoscape network view (FR-DC-040)
from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QWidget

from limes_desktop.state import QueryOutcomeBundle, SessionState
from limes_desktop.views.viz.bridge import bundle_graph, network_payload
from limes_desktop.views.viz.page import VizPage

__all__ = ["NetworkView"]


class NetworkView(VizPage):
    """Cytoscape graph of the current bundle; expand = entity_neighbors delta."""

    def __init__(self, state: SessionState, parent: QWidget | None = None) -> None:
        super().__init__("network.html", state, parent)

    def serialize(self, bundle: QueryOutcomeBundle) -> str:
        return network_payload(bundle)

    def apply_neighbors(self, entity_id: str, graph: Any) -> str:
        """Merge an entity_neighbors delta into the current payload (FR-DC-040).

        `graph` is a GraphNeighbors; MainWindow calls this after the API call
        and pushes the returned JSON to the page.
        """
        from limes_desktop.api.models import GraphResult

        base = bundle_graph(
            QueryOutcomeBundle(result=self._last_graph(), coverage=None, source="expand")
        )
        nodes = {n.entity_id: n for n in base.nodes}
        edges = list(base.edges)
        nodes[graph.entity.entity_id] = graph.entity
        for row in graph.neighbors:
            nodes[row.neighbor.entity_id] = row.neighbor
            edges.append(row.edge)
        merged = GraphResult(nodes=list(nodes.values()), edges=edges)
        return network_payload(
            QueryOutcomeBundle(result=merged, coverage=None, source="expand")
        )

    def _last_graph(self) -> Any:
        from limes_desktop.api.models import GraphResult

        bundles = self._state.history()
        for bundle in reversed(bundles):
            if isinstance(bundle.result, GraphResult):
                return bundle.result
        return GraphResult()
