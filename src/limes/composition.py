# src/limes/composition.py | v1.0.0 | introduced by WP-26
"""Construct runtime resources in dependency order.

Structured-only contexts load no spaCy models or inference clients. Paid inference
uses a passive CostRecorder; legacy budget arguments are accepted and ignored.
Ontology provisioning and dimension-checked embedding construction remain here.
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
from limes.cost.recorder import CostRecorder
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
    """API query resources with passive inference accounting."""

    settings: Settings
    ontology: Ontology
    driver: GraphDriver
    client: OpenRouterClient
    recorder: CostRecorder


def build_run_context(
    settings: Settings,
    *,
    needs_inference: bool,
    budget_eur: Decimal | None = None,
) -> RunContext:
    """Construct every component one run needs, in dependency order.

    Idempotent `provision()` (with the ontology downgrade guard, §4.3) runs
    on every construction. `budget_eur` is a deprecated ignored argument.
    """
    ontology = load_ontology(settings.ontology_path)
    driver = GraphDriver(
        settings.neo4j_uri,
        settings.neo4j_user,
        settings.neo4j_password,
        settings.neo4j_database,
    )
    provision(driver, ontology, settings.embedding_dimensions)
    registry = build_default_registry(
        bundestag_dip_api_key=settings.bundestag_dip_api_key.get_secret_value()
    )
    archive = build_archive_store(settings)
    recorder = CostRecorder(driver)

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
    client = OpenRouterClient(settings, recorder)
    extractor = extractor_for(settings, client)
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
        recorder=recorder,
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
    """API-side inference resources with passive cost recording."""
    recorder = CostRecorder(driver)
    client = OpenRouterClient(settings, recorder)
    return NlqContext(
        settings=settings,
        ontology=ontology,
        driver=driver,
        client=client,
        recorder=recorder,
    )


def extractor_for(settings: Settings, client: OpenRouterClient) -> Extractor:
    """The extractor construction point (WP-29/30): one place for the
    production extractor and the per-candidate extractors the measured
    model-selection stage evaluates, so AC-40's construction surface stays
    in this file. The candidate model rides in a `Settings` copy — the
    extractor reads `extraction_model` from the settings it was given.

    The §8.7.1 protocol declares a settable `model_id`; the extractor
    exposes it as a read-only property (WP-22 made it immutable on
    purpose — the pinned model must not change mid-process). The seam
    site narrows with a cast; the protocol keeps the spec's literal
    shape (D-41).
    """
    return cast(Extractor, OpenRouterExtractor(settings, client))


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


def build_archive_store(settings: Settings, *, create: bool = True) -> ArchiveStore:
    """Shared infrastructure factory for worker and authenticated evidence reads."""
    if create:
        return ArchiveStore(settings.archive_path)
    return ArchiveStore(settings.archive_path, create=False)
