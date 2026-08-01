# src/limes/resolution/resolve.py | v1.0.0 | introduced by WP-25
"""The mention-to-entity converter per Technical Specification §8.8.4.

`resolve_assertions` is the named converter the spec required (its absence in
v1.x meant no module owned the step §3.5 of the design document described in
prose): it turns pre-resolution `ExtractedAssertion` objects — whose
endpoints are mentions — into resolved `Assertion` objects whose endpoints
are identified, creating a `:Mention` node per extracted endpoint and a
scored `SAME_AS` link for every resolved one (§8.8.5).

Resolution routes through the four §8.8.3 bands in order, per unique
(type, normalized surface) within one document:

1. **Deterministic key** — `keys.deterministic_key`, or a Wikidata
   enrichment hit (`wikidata_qid` declared for the type): link, confidence
   1.0, no paid call.
2. **Embed + candidates** — one embedding call for the document's unresolved
   mentions (blocking.embed, cached per text and model), then the §5.3
   vector index query per mention.
3. **Thresholds** — auto-link at `cosine ≥ LIMES_ER_AUTOLINK_COSINE` with
   margin ≥ `LIMES_ER_AUTOLINK_MARGIN` (margin is top minus second score,
   second being zero when only one candidate exists); one adjudication call
   at `cosine ≥ LIMES_ER_ADJUDICATE_COSINE` (or above the auto-link cosine
   with insufficient margin); otherwise mint a new `entity_id`.
4. **Mint** — a deterministic digest over (type, normalized surface), so a
   re-extraction of the same document mints the same identity and the loader
   merges instead of duplicating.

The resolver never writes an entity node (§8.8.3, AC-17): the mint branch
returns an `EntityEndpoint` and the loader materializes it. It also never
links a minted mention — the entity node does not exist until the loader
runs, and creating the relationship would create the node.

**Provenance contract (the pipeline stamps the pipeline-known fields).** The
resolver fills what its context determines: `ontology_version` (from the
loaded ontology), `confidence` (the extraction confidence, carried through —
the resolution confidence lives on the `SAME_AS` link per §8.8.3),
`evidence_document_id`, and the evidence span. The five fields only the
pipeline knows — `source_id`, `source_trust`, `extractor_model`,
`prompt_version`, `schema_version` — are filled with type-satisfying
intermediate values and are contractually re-stamped by `execute_run` before
load (Doc 2 §15.2: "Assertion.source_id | execute_run, from the registry"),
which also recomputes `assertion_id` with the real `source_id`. The
intermediate values never reach the graph.

`RunContext` is defined here (the module that consumes it), following the
D-22 precedent that placed `GateContext` in `pipeline/gate.py`; the
composition root (WP-26) constructs it from the §8.15 shape.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal

import structlog
from pydantic import BaseModel

from limes.archive.store import ArchiveStore
from limes.config import Settings
from limes.cost.governor import Governor
from limes.errors import ExtractionError, SourceFetchError
from limes.extraction.base import Extractor
from limes.extraction.openrouter_client import OpenRouterClient
from limes.graph.driver import GraphDriver
from limes.ontology.model import Ontology
from limes.resolution import adjudicate, blocking, keys, link
from limes.sources.base import deterministic_assertion_id, hash_entity_id, key_entity_id
from limes.sources.registry import SourceRegistry
from limes.sources.wikidata import WikidataAdapter, WikidataMatch
from limes.types import (
    Assertion,
    DocumentPayload,
    EntityEndpoint,
    ExtractedAssertion,
    Mention,
    Provenance,
    Validity,
)

if TYPE_CHECKING:
    from limes.pipeline.gate import GateContext

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class RunContext:
    """The §8.15 run context: everything one pipeline run needs, constructed
    by the composition root (WP-26). `governor`, `client`, `extractor`, and
    `gate` are None on structured-only runs; resolution requires a client."""

    settings: Settings
    ontology: Ontology
    driver: GraphDriver
    registry: SourceRegistry
    archive: ArchiveStore
    governor: Governor | None = None
    client: OpenRouterClient | None = None
    extractor: Extractor | None = None
    gate: GateContext | None = None


class ResolutionStats(BaseModel):
    """Per-band counters for one `resolve_assertions` call (Doc 2 §8.8.4),
    counting endpoint occurrences — each extracted endpoint resolves in
    exactly one band."""

    deterministic: int = 0
    auto_linked: int = 0
    adjudicated: int = 0
    minted: int = 0


@dataclass(frozen=True)
class _Resolution:
    """One resolved mention: the endpoint identity, the band it resolved in,
    and the link score (1.0 for deterministic, the cosine for auto-links,
    the capped adjudicator confidence)."""

    endpoint: EntityEndpoint
    band: Literal["deterministic", "auto", "adjudicated", "mint"]
    score: float


# (type, normalized surface) -> enrichment result, kept for the process: a
# backfill run re-encounters the same surfaces across documents, and each
# hit saved is a network round trip not made. A miss is cached too — a
# mention that failed enrichment once will fail again.
_ENRICH_CACHE: dict[tuple[str, str], WikidataMatch | None] = {}


def resolve_assertions(
    extracted: list[ExtractedAssertion],
    ctx: RunContext,
    doc: DocumentPayload,
) -> tuple[list[Assertion], ResolutionStats]:
    """Convert pre-resolution assertions to resolved ones (AC-43).

    Creates one `:Mention` node per extracted endpoint, resolves each unique
    mention through the §8.8.3 bands, links the resolved ones with `SAME_AS`,
    and assembles the assertions with the resolver-determinable provenance
    (see the module docstring for the pipeline-stamping contract).
    """
    if ctx.client is None:
        raise ExtractionError("resolve_assertions requires an inference client (RunContext.client)")
    if not ctx.settings.embedding_model:
        raise ExtractionError("no embedding model pinned; run select-models first")
    if not ctx.settings.adjudication_model:
        raise ExtractionError("no adjudication model pinned; run select-models first")

    stats = ResolutionStats()
    now = datetime.now(UTC)
    resolutions: dict[tuple[str, str], _Resolution] = {}
    pending: list[tuple[tuple[str, str], Mention, str]] = []
    occurrences: list[tuple[ExtractedAssertion, Mention, str]] = []

    for item in extracted:
        for role in (item.subject, item.object):
            key = (role.type, role.surface.casefold())
            start, end = _locate_offsets(doc, role.surface, item.evidence_start, item.evidence_end)
            mention_id = link.create_mention(ctx.driver, role, doc.content_hash, start, end)
            occurrences.append((item, role, mention_id))
            if key in resolutions:
                continue
            deterministic = keys.deterministic_key(role, ctx.ontology)
            if deterministic is not None:
                resolutions[key] = _Resolution(
                    endpoint=EntityEndpoint(
                        entity_id=key_entity_id(deterministic),
                        type=role.type,
                        label=role.surface,
                        deterministic_key=deterministic,
                        aliases=[role.surface],
                    ),
                    band="deterministic",
                    score=1.0,
                )
                continue
            enriched = _enrich(role, ctx)
            if enriched is not None:
                resolutions[key] = _Resolution(
                    endpoint=EntityEndpoint(
                        entity_id=key_entity_id(("wikidata_qid", enriched.qid)),
                        type=role.type,
                        label=enriched.label,
                        deterministic_key=("wikidata_qid", enriched.qid),
                        aliases=[role.surface],
                    ),
                    band="deterministic",
                    score=1.0,
                )
                continue
            pending.append((key, role, _mention_text(role, doc, item)))

    if pending:
        vectors = blocking.embed(
            [text for _, _, text in pending],
            ctx.client,
            ctx.settings.embedding_model,
            ctx.settings.embedding_dimensions,
        )
        for (key, role, _), vector in zip(pending, vectors, strict=True):
            candidates = blocking.candidates(
                ctx.driver,
                vector,
                role.type,
                ctx.settings.er_candidate_limit,
            )
            resolutions[key] = _route(candidates, role, ctx)

    for _item, role, mention_id in occurrences:
        resolution = resolutions[(role.type, role.surface.casefold())]
        if resolution.band == "deterministic":
            stats.deterministic += 1
        elif resolution.band == "auto":
            stats.auto_linked += 1
        elif resolution.band == "adjudicated":
            stats.adjudicated += 1
        else:
            stats.minted += 1
        if resolution.band != "mint":
            link.link(
                ctx.driver,
                mention_id,
                resolution.endpoint.entity_id,
                resolution.band,
                resolution.score,
                now,
            )
        logger.info(
            "mention resolved",
            surface=role.surface,
            type=role.type,
            band=resolution.band,
            entity_id=resolution.endpoint.entity_id,
            score=resolution.score,
        )

    assertions = [_assemble(item, resolutions, ctx, doc, now) for item in extracted]
    logger.info(
        "resolution completed",
        assertions=len(assertions),
        mentions=len(occurrences),
        deterministic=stats.deterministic,
        auto_linked=stats.auto_linked,
        adjudicated=stats.adjudicated,
        minted=stats.minted,
    )
    return assertions, stats


def _route(
    candidates: list[dict[str, str | float]],
    mention: Mention,
    ctx: RunContext,
) -> _Resolution:
    """The §8.8.3 threshold routing for one mention. The stats counters are
    updated per endpoint occurrence in the caller, after all resolutions are
    cached; the mint band writes no link (see module docstring)."""
    if not candidates:
        return _mint(mention, ctx)
    top_score = float(candidates[0]["score"])
    second_score = float(candidates[1]["score"]) if len(candidates) > 1 else 0.0
    margin = top_score - second_score
    if top_score >= ctx.settings.er_autolink_cosine and margin >= ctx.settings.er_autolink_margin:
        return _Resolution(
            endpoint=_endpoint_from_candidate(candidates[0], mention),
            band="auto",
            score=top_score,
        )
    if top_score >= ctx.settings.er_adjudicate_cosine:
        entity_id, confidence = adjudicate.adjudicate(
            mention,
            candidates,
            ctx.client,  # type: ignore[arg-type]  # checked by the caller
            ctx.settings.adjudication_prompt_version,
            ctx.settings.adjudication_model,
        )
        if entity_id is not None:
            return _Resolution(
                endpoint=_endpoint_from_candidate(candidates[0], mention),
                band="adjudicated",
                score=confidence,
            )
        return _mint(mention, ctx)
    return _mint(mention, ctx)


def _mint(mention: Mention, ctx: RunContext) -> _Resolution:
    """A new identity: a deterministic digest over (type, normalized
    surface), so re-extracting the same document mints the same entity and
    the loader merges it (AC-05 semantics for the extraction path)."""
    return _Resolution(
        endpoint=EntityEndpoint(
            entity_id=hash_entity_id(mention.type.lower(), mention.surface.casefold()),
            type=mention.type,
            label=mention.surface,
            aliases=[mention.surface],
        ),
        band="mint",
        score=0.0,
    )


def _endpoint_from_candidate(candidate: dict[str, str | float], mention: Mention) -> EntityEndpoint:
    """The endpoint for a linked band: the candidate's canonical identity
    and label, with the mention surface offered as an alias (the loader adds
    unseen aliases on merge, so the surface becomes fulltext-findable)."""
    return EntityEndpoint(
        entity_id=str(candidate["entity_id"]),
        type=mention.type,
        label=str(candidate["label"]),
        aliases=[mention.surface],
    )


def _assemble(
    item: ExtractedAssertion,
    resolutions: dict[tuple[str, str], _Resolution],
    ctx: RunContext,
    doc: DocumentPayload,
    now: datetime,
) -> Assertion:
    """One resolved assertion. The validity defaults an unstated `valid_from`
    to the resolution instant — an extracted fact without a stated date is
    current as of now. `assertion_id` is the D-10 digest over the fields the
    resolver knows; `execute_run` recomputes it with the real `source_id`
    (§15.2, module docstring)."""
    subject = resolutions[(item.subject.type, item.subject.surface.casefold())].endpoint
    object_ = resolutions[(item.object.type, item.object.surface.casefold())].endpoint
    validity = Validity(
        valid_from=item.valid_from or now,
        valid_to=item.valid_to,
        recorded_at=now,
    )
    provenance = Provenance(
        source_id="",  # re-stamped by execute_run (§15.2)
        source_trust=0.0,  # re-stamped by execute_run (§15.2)
        confidence=item.confidence,
        extractor_model=None,  # stamped by execute_run
        prompt_version=None,  # stamped by execute_run
        schema_version=None,  # stamped by execute_run
        ontology_version=ctx.ontology.version,
        evidence_document_id=doc.content_hash,
        evidence_start=item.evidence_start,
        evidence_end=item.evidence_end,
    )
    return Assertion(
        assertion_id=deterministic_assertion_id(
            "",
            item.relation,
            subject.entity_id,
            object_.entity_id,
            validity.valid_from,
            validity.valid_to,
        ),
        subject=subject,
        relation=item.relation,
        object=object_,
        validity=validity,
        provenance=provenance,
    )


def _mention_text(mention: Mention, doc: DocumentPayload, item: ExtractedAssertion) -> str:
    """The text embedded for a mention: surface plus inferred type plus the
    evidence sentence as the contextual qualifier (§8.8.2)."""
    qualifier = doc.body[item.evidence_start : item.evidence_end]
    return f"{mention.surface} ({mention.type}) — {qualifier}"


def _locate_offsets(
    doc: DocumentPayload,
    surface: str,
    evidence_start: int,
    evidence_end: int,
) -> tuple[int, int]:
    """The mention's document offsets, anchored on the evidence span.

    The evidence-span check (AC-13) guarantees one of the two surfaces is
    inside the span; the other is in the same passage, which can extend
    beyond it. Search forward from the span start, then backward from it;
    a surface absent from the document entirely (impossible for extractor
    output, which is verbatim document text) is zeroed with a logged
    warning — counted, never silent.
    """
    hay = doc.body.casefold()
    needle = surface.casefold()
    start = hay.find(needle, evidence_start)
    if start < 0:
        start = hay.rfind(needle, 0, evidence_start)
    if start < 0:
        logger.warning(
            "mention surface not found in document; offsets zeroed",
            surface=surface,
            document_id=doc.content_hash,
        )
        return 0, 0
    return start, start + len(surface)


def _enrich(mention: Mention, ctx: RunContext) -> WikidataMatch | None:
    """Wikidata enrichment of a key-less mention: one unambiguous exact-label
    match becomes a `wikidata_qid` deterministic key (confidence 1.0). Only
    types that declare `wikidata_qid` are enriched — a QID the loader cannot
    stamp would mint a second node instead of resolving. A miss, an
    ambiguous result, an absent adapter, or a network failure is `None`,
    each logged; enrichment is a hint, never a guess."""
    if "wikidata_qid" not in ctx.ontology.entity_types[mention.type].identifying_keys:
        return None
    cache_key = (mention.type, mention.surface.casefold())
    if cache_key in _ENRICH_CACHE:
        return _ENRICH_CACHE[cache_key]
    try:
        adapter = ctx.registry.get("wikidata")
    except SourceFetchError:
        logger.warning("wikidata adapter absent from registry; enrichment skipped")
        _ENRICH_CACHE[cache_key] = None
        return None
    if not isinstance(adapter, WikidataAdapter):
        logger.warning("registered wikidata adapter is not a WikidataAdapter; enrichment skipped")
        _ENRICH_CACHE[cache_key] = None
        return None
    try:
        match = adapter.enrich(mention.type, mention.surface)
    except SourceFetchError as exc:
        logger.warning("wikidata enrichment failed; treated as a miss", reason=str(exc))
        match = None
    _ENRICH_CACHE[cache_key] = match
    return match
