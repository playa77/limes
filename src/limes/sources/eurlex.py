# src/limes/sources/eurlex.py | v1.0.0 | introduced by WP-12
"""EUR-Lex adapter per Technical Specification §8.5.2 (source: `eurlex`).

Loads EU legal acts as `LegalAct` entities (deterministic key: CELEX number),
their adopting bodies as `IGO` entities (Wikidata QID), and their cross-act
and topic relations: `ADOPTED`, `AMENDS`, `REPEALS`, `CITES`, `ABOUT_TOPIC`,
`APPLIES_TO`. The source is the Cellar SPARQL endpoint; each response is one
SPARQL JSON results document.

The window is honored at the source: `since`/`until` are compiled into a
FILTER on the adoption date inside the query text, so the endpoint never
returns acts adopted outside the window. The query travels as a GET with the
query parameter URL-encoded because `fetch_bytes` (shared by every adapter)
is a GET helper; the Cellar endpoint accepts GET (verified live).

Two choices are closed by the data available, and the parser stays honest
about both:

- The author-to-QID mapping is a closed constant (`Council of the European
  Union` -> Q8897, `European Parliament` -> Q8889). These are the only two
  names whose Wikidata identifiers are fixed by the adapter; an unknown name
  skips the `ADOPTED` assertion and is counted, because inventing a QID is
  worse than missing the edge.
- A SPARQL row carries topic/apply codes but no topic label, so a `Topic`
  endpoint's label is its code. The multi-key Topic identity (ontology
  `identifying_keys: [vocabulary, code]`) is expressed as the deterministic
  key `("code", code)` with the vocabulary embedded in `entity_id`
  (`topic:EuroVoc:2421`) — the loader stamps one key property, so the
  vocabulary cannot be a second key; this scheme is shared by all adapters.

`AMENDS`, `REPEALS`, and `CITES` are `temporal: false` in the ontology and
never carry `valid_to`. In the absence of a row's adoption date, `valid_from`
falls back to the fetch instant (the same rule as every adapter).
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any, Literal
from urllib.parse import urlencode

import structlog

from limes.errors import SourceParseError
from limes.sources.base import (
    ONTOLOGY_VERSION,
    deterministic_assertion_id,
    fetch_bytes,
    key_entity_id,
    now_utc,
    payload_hash,
)
from limes.types import (
    Assertion,
    EntityEndpoint,
    NormalizedRecord,
    Provenance,
    RawRecord,
    Validity,
)

logger = structlog.get_logger(__name__)

# Verified live (2026-08): the Cellar SPARQL endpoint answers GET with a
# URL-encoded `query` parameter and `format=json`.
SPARQL_URL = "https://publications.europa.eu/webapi/rdf/sparql"

SPARQL_CONTENT_TYPE = "application/json"

# Closed mapping of adopting-body names to Wikidata QIDs. Only these two are
# pinned; any other name skips ADOPTED and is counted (see module docstring).
AUTHOR_QIDS: dict[str, str] = {
    "Council of the European Union": "Q8897",
    "European Parliament": "Q8889",
}

# The `{date_filter}` line is replaced with the adoption-date FILTER compiled
# from the fetch window, or with nothing for an unfiltered full load.
_QUERY_TEMPLATE = """\
PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
PREFIX dc: <http://purl.org/dc/elements/1.1/>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
SELECT DISTINCT ?celex ?title ?date ?author
       ?amends_celex ?repeals_celex ?cites_celex
       ?topic_code ?topic_voc ?applies_to_voc ?applies_to_code
WHERE {
  ?act cdm:resource-legal-id-celex ?celex .
  OPTIONAL { ?act cdm:work-date-document ?date . }
  OPTIONAL { ?act dc:title ?title . }
  OPTIONAL {
    ?act cdm:responsible_legal ?body .
    ?body skos:prefLabel ?author .
  }
  OPTIONAL { ?act cdm:amends_legal ?amended . ?amended cdm:resource-legal-id-celex ?amends_celex . }
  OPTIONAL {
    ?act cdm:repeals_legal ?repealed .
    ?repealed cdm:resource-legal-id-celex ?repeals_celex .
  }
  OPTIONAL { ?act cdm:cites_legal ?cited . ?cited cdm:resource-legal-id-celex ?cites_celex . }
  OPTIONAL {
    ?act cdm:subject-matter-eurovoc ?topic .
    ?topic cdm:resource-id ?topic_code .
    BIND("EuroVoc" AS ?topic_voc)
  }
  OPTIONAL {
    ?act cdm:applies-to ?applies .
    ?applies cdm:resource-id ?applies_to_code .
    BIND("EuroVoc" AS ?applies_to_voc)
  }
  {date_filter}
}
"""


class EurlexAdapter:
    """EUR-Lex — EU legal acts, adopting bodies, citations, topics."""

    source_id: str = "eurlex"
    name: str = "EUR-Lex"
    kind: Literal["structured", "unstructured"] = "structured"
    trust_rank: float = 1.00
    supports_backfill: bool = True
    supports_incremental: bool = True

    def fetch(self, since: datetime | None, until: datetime | None) -> Iterator[RawRecord]:
        """Query Cellar SPARQL for acts adopted in the window.

        The window is compiled into the query text (a FILTER on the adoption
        date), so an incremental run re-fetches only the newly adopted acts.
        Yields one `RawRecord` per response.
        """
        query = _build_query(since, until)
        url = f"{SPARQL_URL}?{urlencode({'query': query, 'format': 'json'})}"
        fetched_at = now_utc()
        payload = fetch_bytes(url)
        logger.info(
            "eurlex payload fetched",
            bytes=len(payload),
            since=since.isoformat() if since else None,
            until=until.isoformat() if until else None,
            fetched_at=fetched_at.isoformat(),
        )
        yield RawRecord(
            payload=payload,
            content_type=SPARQL_CONTENT_TYPE,
            source_url=SPARQL_URL,
            fetched_at=fetched_at,
        )

    def normalize(self, record: RawRecord) -> NormalizedRecord:
        """One SPARQL JSON results document -> assertions.

        Rows without a CELEX are skipped and counted; an unknown adopting
        body skips only its `ADOPTED` assertion, again counted. Nothing is
        dropped unlogged.
        """
        try:
            data = json.loads(record.payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SourceParseError(f"eurlex: payload is not valid JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise SourceParseError("eurlex: SPARQL JSON payload is not an object")
        results = data.get("results")
        bindings = results.get("bindings") if isinstance(results, dict) else None
        if not isinstance(bindings, list):
            raise SourceParseError("eurlex: SPARQL JSON payload has no results.bindings")

        assertions: list[Assertion] = []
        skipped: Counter[str] = Counter()
        for row in bindings:
            assertions.extend(self._normalize_row(row, record, skipped))
        logger.info(
            "eurlex: normalized",
            bindings=len(bindings),
            assertions=len(assertions),
            skipped=dict(skipped) if skipped else None,
            source_id=self.source_id,
        )
        return NormalizedRecord(
            content_hash=payload_hash(record.payload),
            kind="structured",
            assertions=assertions,
        )

    def _normalize_row(
        self,
        row: Any,
        record: RawRecord,
        skipped: Counter[str],
    ) -> list[Assertion]:
        if not isinstance(row, dict):
            skipped["malformed_binding"] += 1
            return []
        celex = _binding_value(row.get("celex"))
        if celex is None:
            skipped["missing_celex"] += 1
            logger.warning("eurlex: binding without celex; skipped")
            return []
        title = _binding_value(row.get("title")) or celex
        valid_from = _valid_from(_binding_value(row.get("date")), record, skipped)

        legal_act = EntityEndpoint(
            entity_id=key_entity_id(("celex", celex)),
            type="LegalAct",
            label=title,
            deterministic_key=("celex", celex),
        )

        assertions: list[Assertion] = []
        author = _binding_value(row.get("author"))
        if author is None:
            skipped["missing_author"] += 1
        elif author not in AUTHOR_QIDS:
            skipped["unknown_author"] += 1
            logger.warning(
                "eurlex: author not in closed mapping; ADOPTED skipped",
                author=author,
                celex=celex,
            )
        else:
            body = EntityEndpoint(
                entity_id=key_entity_id(("wikidata_qid", AUTHOR_QIDS[author])),
                type="IGO",
                label=author,
                deterministic_key=("wikidata_qid", AUTHOR_QIDS[author]),
            )
            assertions.append(_assertion(self, "ADOPTED", body, legal_act, valid_from, record))

        # One row may carry several citation targets when the result groups
        # them; `_binding_values` tolerates both a single and a list binding.
        for relation, variable in (
            ("AMENDS", "amends_celex"),
            ("REPEALS", "repeals_celex"),
            ("CITES", "cites_celex"),
        ):
            for target in _binding_values(row.get(variable)):
                target_act = EntityEndpoint(
                    entity_id=key_entity_id(("celex", target)),
                    type="LegalAct",
                    label=target,
                    deterministic_key=("celex", target),
                )
                assertions.append(
                    _assertion(self, relation, legal_act, target_act, valid_from, record)
                )

        topic_code = _binding_value(row.get("topic_code"))
        topic_voc = _binding_value(row.get("topic_voc"))
        if topic_code is not None and topic_voc is not None:
            assertions.append(
                _assertion(
                    self,
                    "ABOUT_TOPIC",
                    legal_act,
                    _topic(topic_voc, topic_code),
                    valid_from,
                    record,
                )
            )
        elif topic_code is not None or topic_voc is not None:
            skipped["incomplete_topic"] += 1
            logger.warning(
                "eurlex: topic code or vocabulary missing; ABOUT_TOPIC skipped",
                celex=celex,
            )

        applies_voc = _binding_value(row.get("applies_to_voc"))
        applies_code = _binding_value(row.get("applies_to_code"))
        if applies_voc is not None and applies_code is not None:
            assertions.append(
                _assertion(
                    self,
                    "APPLIES_TO",
                    legal_act,
                    _topic(applies_voc, applies_code),
                    valid_from,
                    record,
                )
            )
        elif applies_voc is not None or applies_code is not None:
            skipped["incomplete_applies_to"] += 1
            logger.warning(
                "eurlex: applies_to vocabulary or code missing; APPLIES_TO skipped",
                celex=celex,
            )
        return assertions


def _build_query(since: datetime | None, until: datetime | None) -> str:
    """Compile the fetch window into the query text as an adoption-date
    FILTER, or leave the query unfiltered for a full load."""
    clauses: list[str] = []
    if since is not None:
        clauses.append(f'?date >= "{since.date().isoformat()}"^^xsd:date')
    if until is not None:
        clauses.append(f'?date <= "{until.date().isoformat()}"^^xsd:date')
    date_filter = " && ".join(clauses)
    # .replace, not .format: the SPARQL braces are format fields and would
    # be misparsed.
    return _QUERY_TEMPLATE.replace(
        "{date_filter}", f"FILTER ({date_filter})" if date_filter else ""
    )


def _binding_value(binding: Any) -> str | None:
    """The literal value of one SPARQL binding, or None when absent."""
    if not isinstance(binding, dict):
        return None
    value = binding.get("value")
    return value if isinstance(value, str) and value else None


def _binding_values(binding: Any) -> list[str]:
    """One or several literal values of a binding; tolerates a list binding
    (a row may carry several targets)."""
    if isinstance(binding, list):
        return [v for v in (_binding_value(b) for b in binding) if v is not None]
    value = _binding_value(binding)
    return [value] if value is not None else []


def _topic(vocabulary: str, code: str) -> EntityEndpoint:
    """A Topic endpoint under the shared multi-key identity convention.

    The ontology declares `[vocabulary, code]` as identifying keys, but the
    loader stamps one key property; the vocabulary therefore rides in the
    `entity_id` while the deterministic key is the code alone. The SPARQL row
    carries no topic label, so the code stands in as label.
    """
    return EntityEndpoint(
        entity_id=f"topic:{vocabulary}:{code}",
        type="Topic",
        label=code,
        deterministic_key=("code", code),
    )


def _valid_from(date_value: str | None, record: RawRecord, skipped: Counter[str]) -> datetime:
    """The row's adoption date as an aware UTC instant, or the fetch instant
    when no date is available — never `datetime.now()` (the recorded_at
    discipline requires the archive's fetch instant, not the run instant).

    SPARQL JSON datetimes may be naive ISO strings; they are pinned to UTC
    midnight so a re-run over the same window produces identical
    `valid_from` values and identical assertion digests.
    """
    if date_value is None:
        return record.fetched_at
    try:
        parsed = datetime.fromisoformat(date_value)
    except ValueError:
        skipped["unparseable_date"] += 1
        logger.warning(
            "eurlex: unparseable adoption date; falling back to fetched_at",
            date=date_value,
        )
        return record.fetched_at
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _assertion(
    adapter: EurlexAdapter,
    relation: str,
    subject: EntityEndpoint,
    object_: EntityEndpoint,
    valid_from: datetime,
    record: RawRecord,
) -> Assertion:
    """One assertion with deterministic id and uniform provenance.

    `valid_to` is always None here: the non-temporal relations (AMENDS,
    REPEALS, CITES) must not carry one, and for the temporal relations no end
    date exists in the source. The validator rejects a `valid_to` on
    non-temporal relations, so none is ever constructed.
    """
    return Assertion(
        assertion_id=deterministic_assertion_id(
            adapter.source_id,
            relation,
            subject.entity_id,
            object_.entity_id,
            valid_from,
        ),
        subject=subject,
        relation=relation,
        object=object_,
        validity=Validity(valid_from=valid_from, recorded_at=record.fetched_at),
        provenance=Provenance(
            source_id=adapter.source_id,
            source_trust=adapter.trust_rank,
            confidence=1.0,
            ontology_version=ONTOLOGY_VERSION,
        ),
    )
