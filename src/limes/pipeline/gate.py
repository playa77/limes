# src/limes/pipeline/gate.py | v1.0.0 | introduced by WP-24
"""The deterministic gate per Technical Specification §8.6.3, DD-06.

`gate_document` filters a document before any paid extraction call: the
content-hash cache check short-circuits at zero cost (before any spaCy model
is loaded), local spaCy NER finds entity spans, and `select_passages` keeps
only the text windows dense enough in mentions to be worth extracting. A
document producing zero passages is gated out with a reason and logged — the
count that WP-27 records in `:IngestionRun.documents_gated_out` starts here;
nothing is dropped silently (Doc 2 §8.6.3, §11).

`GateContext` is defined here (the module that consumes it) with the §8.15
shape — `settings`, `driver`, and the two preloaded spaCy models. The
composition root (WP-26) constructs it; the gate never loads a model itself.

`select_passages` is the pure, dependency-free half: given the text, the
language (used only for the model-independent splitter — the entities arrive
already extracted), the recognized entity spans, and the two thresholds, it
returns the passages. The mention threshold is applied here, to sentence
indices; `passages.window_passages` builds the merged windows around the
surviving centers.
"""

from __future__ import annotations

from dataclasses import dataclass

import structlog
from spacy import Language  # type: ignore[attr-defined]

from limes.config import Settings
from limes.graph.driver import GraphDriver
from limes.pipeline import idempotency
from limes.pipeline import passages as passages_module
from limes.types import DocumentPayload, GateDecision, NerSpan, Passage

logger = structlog.get_logger(__name__)

# spaCy NER labels that do not denote entities worth extracting — dates,
# numbers, and percentages would skew the mention-density count and drive
# passages around empty numbers. The set is the refresh point for new model
# label sets.
_NON_ENTITY_LABELS = frozenset(
    {"DATE", "TIME", "PERCENT", "MONEY", "QUANTITY", "ORDINAL", "CARDINAL", "LANGUAGE"}
)


@dataclass(frozen=True)
class GateContext:
    """Everything `gate_document` needs, constructed by the composition root
    (Doc 2 §8.15): settings for the thresholds and version triple, the driver
    for the cache check, and the two preloaded spaCy models."""

    settings: Settings
    driver: GraphDriver
    nlp_de: Language
    nlp_en: Language


def gate_document(
    doc: DocumentPayload, ctx: GateContext, *, skip_cache: bool = False
) -> GateDecision:
    """The gate: cache check, NER, passage selection. Returns the decision;
    every rejection carries its reason (AC-11) and is logged — the pipeline
    run counts `documents_gated_out` from the decisions, never from silence.
    """
    settings = ctx.settings
    if not skip_cache and idempotency.is_already_extracted(
        ctx.driver,
        doc.content_hash,
        settings.extraction_prompt_version,
        settings.extraction_schema_version,
        settings.extraction_model,
    ):
        return GateDecision(passed=False, reason="cache_hit", passages=[])

    nlp = _model_for(doc.language, ctx)
    if nlp is None:
        logger.warning(
            "document gated out: unsupported language",
            content_hash=doc.content_hash,
            language=doc.language,
        )
        return GateDecision(passed=False, reason="unsupported_language", passages=[])

    text = doc.body if doc.news_metadata is not None else f"{doc.title}\n\n{doc.body}"
    entities = [
        NerSpan(text=ent.text, label=ent.label_, start=ent.start_char, end=ent.end_char)
        for ent in nlp(text).ents
        if ent.label_ not in _NON_ENTITY_LABELS
    ]
    passages = select_passages(
        text,
        doc.language,
        entities,
        settings.extraction_passage_window_sentences,
        settings.gate_min_entity_mentions,
    )
    if not passages:
        logger.info(
            "document gated out: below mention threshold",
            content_hash=doc.content_hash,
            language=doc.language,
            entity_spans=len(entities),
        )
        return GateDecision(passed=False, reason="below_mention_threshold", passages=[])

    logger.info(
        "document passed the gate",
        content_hash=doc.content_hash,
        passages=len(passages),
        entity_spans=len(entities),
    )
    return GateDecision(passed=True, reason="passed", passages=passages)


def select_passages(
    text: str,
    language: str,
    entities: list[NerSpan],
    window_sentences: int,
    min_mentions: int,
) -> list[Passage]:
    """Passages around sentences with at least `min_mentions` recognized
    entities. `language` selects nothing here (the splitter is language-
    independent for the two supported languages); it is part of the signature
    per §8.6.3. A sentence qualifies when that many entity spans overlap its
    span; the qualified sentence indices become the window centers.
    """
    sentence_spans = passages_module.split_sentences(text)
    if not sentence_spans:
        return []
    centers: list[int] = []
    for index, (start, end, _sentence) in enumerate(sentence_spans):
        mentions = sum(1 for entity in entities if entity.start < end and entity.end > start)
        if mentions >= min_mentions:
            centers.append(index)
    return passages_module.window_passages(
        text,
        [sentence for (_start, _end, sentence) in sentence_spans],
        centers,
        window_sentences,
    )


def _model_for(language: str, ctx: GateContext) -> Language | None:
    """The preloaded spaCy model for the document language; None for anything
    but `de`/`en` (the two languages the extraction pipeline accepts)."""
    if language == "de":
        return ctx.nlp_de
    if language == "en":
        return ctx.nlp_en
    return None
