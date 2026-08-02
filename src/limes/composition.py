# src/limes/composition.py | v1.0.0 | introduced by WP-26
"""The composition root per Technical Specification §8.15 (DD-18, C-07).

The single module that constructs every component the system needs, in
dependency order, once per process. Nothing below the CLI or the API
startup handler instantiates a driver, registry, archive, governor,
client, extractor, or gate (AC-40); the two build functions here are the
only construction surface.

`needs_inference` is the resource contract (AC-41): a structured-only run
loads no spaCy model and constructs no extractor, leaving the inference
slots None — the run stays inside the RAM-and-key contract of a
deterministic load.

The context types are owned by their consumers, per the D-22/D-28
precedent: `RunContext` lives in `resolution/resolve.py`, `GateContext`
in `pipeline/gate.py`. Only `NlqContext` is defined here — its consumer
(`api/deps.py`, WP-32) does not exist yet, and §8.15 is its named home.

`embedder_for` is the WP-26 wiring point D-26 named: `load()` cannot see
Settings, so the declared-dimension check on the embeddings it stamps
lives here, at the callable's construction. The loader additionally
re-normalizes whatever it receives (`graph/embeddings.py`).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import cast

import spacy
import structlog

from limes.archive.store import ArchiveStore
from limes.config import Settings
from limes.cost.governor import Governor
from limes.extraction.base import Extractor
from limes.extraction.openrouter import OpenRouterExtractor
from limes.extraction.openrouter_client import OpenRouterClient
from limes.graph.driver import GraphDriver
from limes.graph.embeddings import normalize_embedding
from limes.graph.schema import provision
from limes.ontology.model import Ontology
from limes.ontology.registry import load_ontology
from limes.pipeline.gate import GateContext
from limes.resolution.resolve import RunContext
from limes.sources.registry import build_default_registry

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class NlqContext:
    """The §8.15 natural-language-query context, constructed by
    `build_nlq_context` for the API startup handler (WP-32). The client is
    paid inference and is metered against the monthly ceiling like every
    other caller."""

    settings: Settings
    ontology: Ontology
    driver: GraphDriver
    client: OpenRouterClient
    governor: Governor


def build_run_context(
    settings: Settings,
    *,
    needs_inference: bool,
    budget_eur: Decimal | None = None,
) -> RunContext:
    """Construct every component one run needs, in dependency order.

    Idempotent `provision()` (with the ontology downgrade guard, §4.3) runs
    on every construction. `budget_eur` gives the governor an envelope
    instead of the monthly ceiling — the backfill/reextract contract that
    keeps the steady-state envelope untouched (AC-15).
    """
    ontology = load_ontology(settings.ontology_path)
    driver = GraphDriver(
        settings.neo4j_uri,
        settings.neo4j_user,
        settings.neo4j_password,
        settings.neo4j_database,
    )
    provision(driver, ontology, settings.embedding_dimensions)
    registry = build_default_registry()
    archive = ArchiveStore(settings.archive_path)
    governor = Governor(
        driver,
        settings.monthly_budget_eur,
        settings.budget_soft_stop_fraction,
        settings.usd_eur_rate,
        envelope_eur=budget_eur,
    )

    if not needs_inference:
        logger.info(
            "run context built (structured only)",
            ontology_version=ontology.version,
            inference_loaded=False,
        )
        return RunContext(
            settings=settings,
            ontology=ontology,
            driver=driver,
            registry=registry,
            archive=archive,
        )

    nlp_de = spacy.load(settings.gate_spacy_model_de)
    nlp_en = spacy.load(settings.gate_spacy_model_en)
    client = OpenRouterClient(settings, governor)
    # The §8.7.1 protocol declares a settable `model_id`; the extractor
    # exposes it as a read-only property (WP-22 made it immutable on
    # purpose — the pinned model must not change mid-process). The seam
    # site narrows with a cast; the protocol keeps the spec's literal
    # shape (D-41).
    extractor = cast(Extractor, OpenRouterExtractor(settings, client))
    logger.info(
        "run context built (with inference)",
        ontology_version=ontology.version,
        inference_loaded=True,
        gate_spacy_model_de=settings.gate_spacy_model_de,
        gate_spacy_model_en=settings.gate_spacy_model_en,
    )
    return RunContext(
        settings=settings,
        ontology=ontology,
        driver=driver,
        registry=registry,
        archive=archive,
        governor=governor,
        client=client,
        extractor=extractor,
        gate=GateContext(
            settings=settings,
            driver=driver,
            nlp_de=nlp_de,
            nlp_en=nlp_en,
        ),
    )


def build_nlq_context(
    settings: Settings,
    ontology: Ontology,
    driver: GraphDriver,
) -> NlqContext:
    """The API-side context: monthly-metered client, no envelope (query
    generation draws on the steady state, §8.15)."""
    governor = Governor(
        driver,
        settings.monthly_budget_eur,
        settings.budget_soft_stop_fraction,
        settings.usd_eur_rate,
    )
    client = OpenRouterClient(settings, governor)
    return NlqContext(
        settings=settings,
        ontology=ontology,
        driver=driver,
        client=client,
        governor=governor,
    )


def embedder_for(
    settings: Settings,
    client: OpenRouterClient | None,
) -> Callable[[list[str]], list[list[float]]] | None:
    """The loader's embedder wiring (D-26): the client's embedding call
    dimension-checked and L2-normalized against the declared
    `LIMES_EMBEDDING_DIMENSIONS`.

    None when no client exists — a structured-only run then writes null
    embeddings, which the §13.3 one-shot backfill fills. The dimension
    check lives here because the loader never sees Settings; a wrong-length
    vector would be silently unindexable in a cosine index.
    """
    if client is None:
        return None

    def _embed(labels: list[str]) -> list[list[float]]:
        vectors = client.embed(labels, settings.embedding_model)
        if len(vectors) != len(labels):
            raise ValueError(f"embedder returned {len(vectors)} vectors for {len(labels)} labels")
        return [normalize_embedding(v, settings.embedding_dimensions) for v in vectors]

    return _embed
