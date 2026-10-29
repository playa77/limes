# src/limes/api/deps.py | v1.0.0 | introduced by WP-32
"""FastAPI dependencies per Technical Specification §8.12 and §15.3 Trace 3.

The application startup handler (`main.py`) loads settings, the ontology,
and the driver once and stores them in `app.state`; the dependencies here
are the routers' only window onto them, so routers contain no business
logic and no construction. `build_nlq_context` is called lazily from this
module on the first query that needs paid inference, per §15.2's seam
(`api/deps.py` → `build_nlq_context`).
"""

from __future__ import annotations

from threading import Lock
from typing import cast

from fastapi import Request

from limes.archive.store import ArchiveStore
from limes.composition import NlqContext, build_archive_store, build_nlq_context
from limes.config import Settings, reload_model_pins
from limes.graph.driver import GraphDriver
from limes.ontology.model import Ontology


def get_settings(request: Request) -> Settings:
    """The settings loaded by the startup handler."""
    return cast(Settings, request.app.state.settings)


def get_ontology(request: Request) -> Ontology:
    """The ontology loaded by the startup handler."""
    return cast(Ontology, request.app.state.ontology)


def get_driver(request: Request) -> GraphDriver:
    """The read-mode driver constructed by the startup handler."""
    return cast(GraphDriver, request.app.state.driver)


def get_nlq_context(request: Request) -> NlqContext:
    """Cache query resources, refreshing atomically published model pins on next use."""
    state = request.app.state
    lock = getattr(state, "nlq_context_lock", None)
    if lock is None:
        lock = Lock()
        state.nlq_context_lock = lock
    with lock:
        current = reload_model_pins(state.settings)
        context = getattr(state, "nlq_context", None)
        if context is None or context.settings != current:
            context = build_nlq_context(current, state.ontology, state.driver)
            state.nlq_context = context
        return cast(NlqContext, context)


def get_archive(request: Request) -> ArchiveStore:
    return build_archive_store(get_settings(request), create=False)
