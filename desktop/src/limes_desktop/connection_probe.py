"""Bounded background connection probes, independent of the GUI event loop."""

from typing import Any

from PySide6.QtCore import QObject, QRunnable, Signal

from limes_desktop.api.errors import ApiError, ApiUnreachable


class ProbeSignals(QObject):
    completed = Signal(int, object)


class ConnectionProbe(QRunnable):
    def __init__(self, generation: int, client: Any) -> None:
        super().__init__()
        self.generation, self.client = generation, client
        self.signals = ProbeSignals()

    def run(self) -> None:
        self.signals.completed.emit(self.generation, probe(self.client))


def probe(client: Any) -> dict[str, Any]:
    try:
        health = client.health()
    except ApiUnreachable:
        return {"status": "unreachable", "version": ""}
    except (ApiError, ValueError):
        return {"status": "degraded", "version": ""}
    except Exception:
        return {"status": "unreachable", "version": ""}
    result: dict[str, Any] = {
        "status": health.status if health.neo4j else "degraded",
        "version": health.ontology_version,
    }
    for name, action in (("ontology", client.ontology),):
        try:
            result[name] = action()
        except Exception:
            pass
    try:
        result["backup"] = bool(client.operation_capabilities().get("backup", False))
    except Exception:
        result["backup"] = False
    return result
