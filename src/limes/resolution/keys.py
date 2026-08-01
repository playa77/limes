# src/limes/resolution/keys.py | v1.0.0 | introduced by WP-25
"""Deterministic key extraction per Technical Specification §8.8.1.

`deterministic_key` turns a mention into an identity — or returns `None`.
When present, resolution terminates with confidence 1.0: no embedding, no
vector query, no adjudication, no paid call (Doc 2 §8.8.1, AC-16). Structured
sources resolve almost entirely through this path, which is why the
structured backbone costs nothing.

Two inputs feed it, in order:

1. The mention's own `deterministic_key` (the extraction model may have
   placed one on the mention), honored only when the key name is declared
   for the inferred type — the same ontology bound the loader applies
   (`graph/loader.py::_key_property`); an undeclared key is ignored with a
   logged warning.
2. Surface-text patterns appropriate to the inferred type.

The pattern table is deliberately conservative: a missed key costs one
embedding and possibly one mint, while a wrong key costs a wrong identity —
the failure mode that matters. Two rules enforce exactness:

- **The produced value must equal the value the structured adapter emits**
  for the same identity, or the deterministic band resolves to a different
  `entity_id` and duplicates the backbone node instead of hitting it.
  Patterns whose surface form is not canonical (register numbers with court
  suffixes, bare-digit ids) are excluded rather than matched partially.
- Every value is either the full match or rebuilt from capture groups into
  the adapter's canonical form (e.g. the BGBl citation's periodikum dot is
  stripped).

The table is the single refresh point for a new pattern: add the type and
the pattern here, nowhere else.
"""

from __future__ import annotations

import re
from collections.abc import Callable

import structlog

from limes.ontology.model import Ontology
from limes.types import Mention

logger = structlog.get_logger(__name__)

# Type -> [(key_name, pattern, value_builder)]. The ontology declares which
# key names a type may carry; the pattern merely finds the value. Patterns
# are word-bounded and uppercase where the format is uppercase (LEI, QID).
# The value builder returns the canonical key value; for most patterns that
# is the full match, for a few it is rebuilt from groups to match the
# adapter's emitted form exactly.


def _full_match(match: re.Match[str]) -> str:
    """The canonical value of a pattern that matches the adapter's emitted
    form verbatim."""
    return match.group(0)


_PATTERNS: dict[str, list[tuple[str, re.Pattern[str], Callable[[re.Match[str]], str]]]] = {
    "Person": [("wikidata_qid", re.compile(r"\bQ\d{1,12}\b"), _full_match)],
    "PublicBody": [("wikidata_qid", re.compile(r"\bQ\d{1,12}\b"), _full_match)],
    "PoliticalParty": [("wikidata_qid", re.compile(r"\bQ\d{1,12}\b"), _full_match)],
    "IGO": [("wikidata_qid", re.compile(r"\bQ\d{1,12}\b"), _full_match)],
    "Corporation": [("lei", re.compile(r"\b[A-Z0-9]{20}\b"), _full_match)],
    "InterestGroup": [("transparency_register_id", re.compile(r"\b\d{12}-\d{2}\b"), _full_match)],
    "LegalAct": [
        ("celex", re.compile(r"\b[1-8]\d{4}[A-Z]{1,2}\d{2,6}\b"), _full_match),
        (
            "bgb_citation",
            re.compile(r"\bBGBl\.?\s*([IVX]{1,3})\s+(\d{4}),\s*(\d{2,5})\b"),
            lambda m: f"BGBl {m.group(1)} {m.group(2)}, {m.group(3)}",
        ),
    ],
    "Contract": [("ted_notice_id", re.compile(r"\b\d{6}-\d{4}\b"), _full_match)],
    "Document": [("content_hash", re.compile(r"\b[0-9a-f]{64}\b"), _full_match)],
}


def deterministic_key(mention: Mention, ontology: Ontology) -> tuple[str, str] | None:
    """A deterministic key for the mention, or `None`.

    The mention-carried key is honored only when declared for the inferred
    type; surface patterns run for the inferred type only. Both are bounded
    by the ontology, so an out-of-ontology key can never leave this module.
    """
    if mention.deterministic_key is not None:
        name, value = mention.deterministic_key
        if _declared(mention.type, name, ontology):
            return (name, value)
        logger.warning(
            "mention-carried deterministic key not declared for type; ignored",
            key_name=name,
            type=mention.type,
        )
    for key_name, pattern, value_builder in _PATTERNS.get(mention.type, []):
        match = pattern.search(mention.surface)
        if match is not None and _declared(mention.type, key_name, ontology):
            return (key_name, value_builder(match))
    return None


def _declared(type_name: str, key_name: str, ontology: Ontology) -> bool:
    """True when the key name is declared for the type — the loader would
    refuse to stamp anything this function returns false for, so the check
    keeps the resolver from minting identity the loader cannot materialize
    (Doc 2 §5.6, `_key_property`)."""
    spec = ontology.entity_types.get(type_name)
    return spec is not None and key_name in spec.identifying_keys
