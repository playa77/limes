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

from typing import cast

from fastapi import Request

from limes.composition import NlqContext, build_nlq_context
from limes.config import Settings
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
    """The `NlqContext` for the query path, built on first use and cached.
    Construction is deferred: the context owns the paid-inference client
    and the monthly governor, which no request should pay for before a
    natural-language query is actually asked."""
    state = request.app.state
    context = getattr(state, "nlq_context", None)
    if context is None:
        context = build_nlq_context(state.settings, state.ontology, state.driver)
        state.nlq_context = context
    return cast(NlqContext, context)
