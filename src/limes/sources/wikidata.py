# src/limes/sources/wikidata.py | v1.0.0 | introduced by WP-18
"""Wikidata adapter per Technical Specification §8.5.2 — enrichment only.

`wikidata` does not ingest. It exposes
`enrich(entity_type, label) -> WikidataMatch | None` for the resolver:
one unambiguous exact-label hit, optionally class-filtered, or None. The
adapter deviates from the SourceAdapter protocol ON PURPOSE and is never run
through `execute_run`; it still declares the protocol's class attributes so
registry code treats it uniformly, and its `fetch`/`normalize` methods raise
`NotImplementedError` — the resolver's caller counts misses, the adapter
never guesses.

Two deliberate choices, both logged by the integrator:

- The source table names SPARQL as the access method, but the SPARQL
  endpoint is unreachable in practice (timeouts since 2024); the read-only
  documented surface, `wbsearchentities`/`wbsgetentities`, is what works and
  what this adapter uses.
- `_CLASS_QIDS` is a closed map from entity type to Wikidata classes; types
  without a stable class (LegalAct, Topic, Contract, Event, Office, Asset,
  AdministrativeRegion, Location, Document, Sanction) get no filter at all.
  This map is the refresh point when a new type needs filtering — add the
  entry there, nowhere else.

Ambiguity is a miss, not a guess: zero exact-label hits or more than one
return None, each with a logged reason and count. A class mismatch is
likewise a counted miss. Network-level failure raises `SourceFetchError` via
`fetch_bytes` (the resolver treats it as a miss at its level); a malformed
response raises `SourceParseError`.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import datetime
from typing import Any
from urllib.parse import urlencode

import structlog
from pydantic import BaseModel

from limes.errors import SourceParseError
from limes.sources.base import fetch_bytes
from limes.types import NormalizedRecord, RawRecord

logger = structlog.get_logger(__name__)

# Both endpoints are the MediaWiki action API; the query parameters are what
# differ between the two calls (verified live from this host, 2026-08).
SEARCH_URL = "https://www.wikidata.org/w/api.php"
ENTITIES_URL = "https://www.wikidata.org/w/api.php"

# Entity type -> Wikidata instance-of classes (P31 values). A candidate whose
# P31 set intersects this list passes the filter; the map is closed, and
# types absent here are not filtered at all.
_CLASS_QIDS: dict[str, list[str]] = {
    "Person": ["Q5"],
    "Corporation": ["Q4830453", "Q6881511", "Q783794"],
    "Country": ["Q6256"],
    "PublicBody": ["Q4164871", "Q327333"],
    "IGO": ["Q484652"],
    "PoliticalParty": ["Q7278"],
    "InterestGroup": ["Q163740"],
}


class WikidataMatch(BaseModel):
    """One resolved Wikidata item for the resolver: stable QID plus the label
    and aliases that justify the match. Ambiguity never reaches this class —
    `enrich` returns None instead."""

    qid: str
    label: str
    aliases: list[str] = []


class WikidataAdapter:
    """Wikidata — read-only enrichment of labels to unambiguous QIDs."""

    source_id = "wikidata"
    name = "Wikidata"
    kind = "structured"
    trust_rank = 0.90
    supports_backfill = False
    supports_incremental = False

    def fetch(self, since: datetime | None, until: datetime | None) -> Iterator[RawRecord]:
        """Not part of the protocol surface for this source: enrichment only,
        never bulk-loaded, never run through `execute_run`."""
        raise NotImplementedError("wikidata is enrichment-only; fetch is not part of its surface")

    def normalize(self, record: RawRecord) -> NormalizedRecord:
        """Not part of the protocol surface for this source: see `fetch`."""
        raise NotImplementedError(
            "wikidata is enrichment-only; normalize is not part of its surface"
        )

    def enrich(self, entity_type: str, label: str) -> WikidataMatch | None:
        """Resolve `label` to one unambiguous Wikidata item, or None.

        An exact label match (casefolded, whitespace collapsed) whose
        `match.type` is `label` may proceed; zero or several hits are a miss,
        never a guess. For types in `_CLASS_QIDS` the candidate must also
        carry a P31 value from the type's class list, checked via a second
        request; unmapped types skip the filter entirely.
        """
        query = _collapse(label)
        search_data = _parse_json(
            fetch_bytes(f"{SEARCH_URL}?{urlencode(_search_params(query))}"), "search"
        )
        results = search_data.get("search")
        if not isinstance(results, list):
            raise SourceParseError("wikidata: search response has no 'search' list")

        candidates: list[dict[str, Any]] = []
        for result in results:
            if not isinstance(result, dict):
                raise SourceParseError("wikidata: search result is not a JSON object")
            match = result.get("match")
            result_label = result.get("label")
            if (
                isinstance(match, dict)
                and match.get("type") == "label"
                and isinstance(result_label, str)
                and _collapse(result_label).casefold() == query.casefold()
            ):
                candidates.append(result)
        logger.info(
            "wikidata: search candidates",
            entity_type=entity_type,
            query=query,
            results=len(results),
            candidates=len(candidates),
        )

        if len(candidates) == 0:
            reason = (
                "no results"
                if not results
                else "no exact label match (alias or description hits only)"
            )
            logger.info(
                "wikidata: enrich miss (not guessed)",
                entity_type=entity_type,
                query=query,
                reason=reason,
                candidates=0,
            )
            return None
        if len(candidates) > 1:
            logger.info(
                "wikidata: enrich miss (not guessed)",
                entity_type=entity_type,
                query=query,
                reason="ambiguous: multiple exact label matches",
                candidates=len(candidates),
            )
            return None

        candidate = candidates[0]
        qid = candidate.get("id")
        if not isinstance(qid, str) or not qid:
            raise SourceParseError("wikidata: search result carries no item id")

        class_qids = _CLASS_QIDS.get(entity_type)
        if class_qids is not None and not _matches_class(qid, class_qids):
            logger.info(
                "wikidata: enrich miss (class mismatch)",
                entity_type=entity_type,
                query=query,
                qid=qid,
                class_qids=class_qids,
            )
            return None

        raw_aliases = candidate.get("aliases")
        if isinstance(raw_aliases, list):
            aliases = [a for a in raw_aliases if isinstance(a, str)]
            if len(aliases) != len(raw_aliases):
                logger.warning(
                    "wikidata: non-string alias dropped from match",
                    qid=qid,
                    dropped=len(raw_aliases) - len(aliases),
                )
        else:
            aliases = []

        match = WikidataMatch(qid=qid, label=candidate["label"], aliases=aliases)
        logger.info(
            "wikidata: enrich hit",
            entity_type=entity_type,
            query=query,
            qid=match.qid,
        )
        return match


def _search_params(query: str) -> dict[str, str]:
    return {
        "action": "wbsearchentities",
        "search": query,
        "language": "de",
        "format": "json",
        "type": "item",
        "limit": "10",
    }


def _entities_params(qid: str) -> dict[str, str]:
    return {
        "action": "wbsgetentities",
        "ids": qid,
        "props": "claims|labels",
        "languages": "de|en",
        "format": "json",
    }


def _matches_class(qid: str, class_qids: list[str]) -> bool:
    """True when the item's P31 claims intersect the class list.

    A claim whose snak carries no `datavalue` (novalue/somevalue) simply
    cannot match a class and is skipped with a count, never fatal.
    """
    entities = _parse_json(
        fetch_bytes(f"{ENTITIES_URL}?{urlencode(_entities_params(qid))}"), "entities"
    )
    entity = entities.get("entities", {}).get(qid)
    if not isinstance(entity, dict):
        raise SourceParseError(f"wikidata: entities response lacks item {qid}")
    claims = entity.get("claims", {})
    statements = claims.get("P31")
    if not isinstance(statements, list):
        return False
    malformed = 0
    for statement in statements:
        if not isinstance(statement, dict):
            malformed += 1
            continue
        snak = statement.get("mainsnak")
        if not isinstance(snak, dict):
            malformed += 1
            continue
        value = snak.get("datavalue", {}).get("value")
        if isinstance(value, dict) and value.get("id") in class_qids:
            return True
    if malformed:
        logger.warning("wikidata: malformed P31 statements skipped", qid=qid, count=malformed)
    return False


def _parse_json(payload: bytes, endpoint: str) -> dict[str, Any]:
    """Decode an API payload into a JSON object, or raise `SourceParseError`.

    Both `wbsetentities`-style responses are objects with an `entities` or
    `search` key; anything else is malformed and treated as a record-level
    skip, never guessed past.
    """
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SourceParseError(f"wikidata: {endpoint} response is not UTF-8") from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SourceParseError(f"wikidata: {endpoint} response is not JSON") from exc
    if not isinstance(data, dict):
        raise SourceParseError(f"wikidata: {endpoint} response is not a JSON object")
    return data


def _collapse(text: str) -> str:
    """Collapse runs of whitespace to single spaces — the comparison form for
    labels, so internal line breaks in API labels cannot mask a match."""
    return " ".join(text.split())
