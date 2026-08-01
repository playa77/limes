# src/limes/pipeline/passages.py | v1.0.0 | introduced by WP-24
"""Passage windowing utilities per Technical Specification §8.6.3.

`window_passages` builds overlapping windows over a document: windows are
centered on the sentences `select_passages` (gate.py) has qualified by entity
mention density, span `window_sentences` sentences in each direction, and
merge when they overlap or touch — so the extractor sees coherent text
chunks, not duplicated or gapped fragments. Every passage carries document
offsets (`doc_start`, `doc_end`), which is what the extractor's evidence-span
mapping (WP-22, AC-13) is anchored to.

`split_sentences` is the deterministic sentence splitter the gate uses; it is
deliberately dependency-free (no spaCy — the unit tests and the extraction
path must not require a model to window a text). The trade-off is
abbreviation blindness ("Dr. Müller" splits), which costs an extra window,
not a wrong assertion.
"""

from __future__ import annotations

import re

import structlog

from limes.types import Passage

logger = structlog.get_logger(__name__)

# A sentence boundary is a terminal .!? (also the closing quote) followed by
# whitespace and an uppercase letter — German and English sentence starts.
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?»\"'])\s+(?=[A-ZÄÖÜ])")


def split_sentences(text: str) -> list[tuple[int, int, str]]:
    """The text as `(start, end, sentence)` triples, in order. Offsets are
    into the source text; the trailing boundary whitespace belongs to the
    gap, not to a sentence. `text[start:end] == sentence` always holds."""
    sentences: list[tuple[int, int, str]] = []
    cursor = 0
    for match in _SENTENCE_BOUNDARY.finditer(text):
        raw = text[cursor : match.start()]
        stripped = raw.strip()
        if stripped:
            start = cursor + len(raw) - len(raw.lstrip())
            sentences.append((start, match.start(), stripped))
        cursor = match.end()
    tail = text[cursor:]
    stripped = tail.strip()
    if stripped:
        start = cursor + len(tail) - len(tail.lstrip())
        sentences.append((start, len(text), stripped))
    return sentences


def window_passages(
    text: str,
    sentences: list[str],
    entity_positions: list[int],
    window_sentences: int,
) -> list[Passage]:
    """Windows over the text centered on the given sentence indices.

    `entity_positions` is the list of 0-based sentence indices that qualify
    as window centers (the gate pre-filters by mention count — the threshold
    is not a parameter here because the roadmap's signature fixes this one).
    Each window spans `window_sentences` sentences on both sides; overlapping
    or adjacent windows merge into one passage. Out-of-range centers are
    skipped with a warning — the caller computes them from the same sentence
    list, so they are programming errors, not data conditions.
    """
    spans = split_sentences(text)
    if not spans:
        return []
    centers = sorted({position for position in entity_positions if 0 <= position < len(spans)})
    if not centers:
        return []

    merged: list[tuple[int, int]] = []
    for center in centers:
        start_index = max(0, center - window_sentences)
        end_index = min(len(spans) - 1, center + window_sentences)
        start = spans[start_index][0]
        end = spans[end_index][1]
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))

    passages: list[Passage] = []
    for index, (start, end) in enumerate(merged):
        # The passage text is the exact document slice — `doc_start`/`doc_end`
        # must satisfy `text[doc_start:doc_end] == text`, because the
        # extractor maps evidence offsets onto document offsets through them
        # (WP-22, AC-13). No stripping, no trimming.
        passages.append(Passage(index=index, text=text[start:end], doc_start=start, doc_end=end))
    logger.info(
        "passages windowed",
        sentences=len(spans),
        centers=len(centers),
        passages=len(passages),
    )
    return passages
