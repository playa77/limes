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
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from urllib.parse import urlencode

import structlog

from limes.errors import SourceFetchError, SourceParseError
from limes.sources.base import (
    fetch_bytes,
    key_entity_id,
    make_assertion,
    now_utc,
    payload_hash,
    topic_endpoint,
)
from limes.types import (
    Assertion,
    EntityEndpoint,
    NormalizedRecord,
    RawRecord,
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
PAGE_SIZE = 5000
_QUERY_TEMPLATE = """\
PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
SELECT DISTINCT ?celex ?title ?date ?author
       ?amends_celex ?repeals_celex ?cites_celex ?topic_code ?topic_voc
WHERE {
  ?act cdm:resource_legal_id_celex ?celex .
  OPTIONAL { ?act cdm:work_date_document ?date . }
  OPTIONAL {
    ?act cdm:work_title ?title .
    FILTER(lang(?title) = "" || langMatches(lang(?title), "en"))
  }
  OPTIONAL {
    ?act cdm:work_created_by_agent ?body .
    BIND(IF(STR(?body) = "http://publications.europa.eu/resource/authority/corporate-body/CONSIL",
            "Council of the European Union",
            IF(STR(?body) = "http://publications.europa.eu/resource/authority/corporate-body/EP",
               "European Parliament", STR(?body))) AS ?author)
  }
  OPTIONAL {
    ?act cdm:resource_legal_amends_resource_legal ?amended .
    ?amended cdm:resource_legal_id_celex ?amends_celex .
  }
  OPTIONAL {
    ?act cdm:resource_legal_repeals_resource_legal ?repealed .
    ?repealed cdm:resource_legal_id_celex ?repeals_celex .
  }
  OPTIONAL { ?act cdm:work_cites_work ?cited . ?cited cdm:resource_legal_id_celex ?cites_celex . }
  OPTIONAL {
    ?act cdm:work_is_about_concept_eurovoc ?topic .
    BIND(REPLACE(STR(?topic), "^.*/", "") AS ?topic_code)
    BIND("EuroVoc" AS ?topic_voc)
  }
  {date_filter}
}
ORDER BY ?celex ?title ?date ?author ?amends_celex ?repeals_celex ?cites_celex ?topic_code
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
        seen_pages: set[str] = set()
        for page in range(40):
            paged = f"{query}\nLIMIT {PAGE_SIZE} OFFSET {page * PAGE_SIZE}"
            url = f"{SPARQL_URL}?{urlencode({'query': paged, 'format': 'json'})}"
            payload = fetch_bytes(url, max_bytes=32 * 1024 * 1024)
            try:
                document = json.loads(payload)
                bindings = document["results"]["bindings"]
                if not isinstance(bindings, list):
                    raise ValueError("bindings is not a list")
            except (ValueError, TypeError, KeyError) as exc:
                raise SourceFetchError("eurlex: invalid SPARQL search response") from exc
            digest = payload_hash(json.dumps(bindings, sort_keys=True).encode())
            if digest in seen_pages:
                raise SourceFetchError("eurlex: repeated SPARQL page; checkpoint unchanged")
            seen_pages.add(digest)
            yield RawRecord(
                payload=payload,
                content_type=SPARQL_CONTENT_TYPE,
                source_url=SPARQL_URL,
                fetched_at=now_utc(),
                acquisition_context={"query": paged, "page": page + 1},
            )
            if len(bindings) < PAGE_SIZE:
                return
        raise SourceFetchError("eurlex: page limit exceeded; submit a narrower window")

    def bound_ingest_window(self, since: datetime, until: datetime) -> datetime:
        return min(since + timedelta(days=1), until)

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
        candidates: dict[str, EntityEndpoint] = {}
        for row in bindings:
            assertions.extend(self._normalize_row(row, record, skipped))
            celex = _binding_value(row.get("celex")) if isinstance(row, dict) else None
            if celex:
                entity = EntityEndpoint(
                    entity_id=key_entity_id(("celex", celex)),
                    type="LegalAct",
                    label=_binding_value(row.get("title")) or celex,
                    deterministic_key=("celex", celex),
                )
                candidates[entity.entity_id] = entity
        involved = {e.entity_id for a in assertions for e in (a.subject, a.object)}
        standalone = [e for key, e in candidates.items() if key not in involved]
        logger.info(
            "eurlex: normalized",
            bindings=len(bindings),
            standalone_entities=len(standalone),
            assertions=len(assertions),
            skipped=dict(skipped) if skipped else None,
            source_id=self.source_id,
        )
        return NormalizedRecord(
            content_hash=payload_hash(record.payload),
            kind="structured",
            assertions=assertions,
            entities=standalone,
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
            assertions.append(
                make_assertion(self, record, body, "ADOPTED", legal_act, valid_from=valid_from)
            )

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
                    make_assertion(
                        self, record, legal_act, relation, target_act, valid_from=valid_from
                    )
                )

        topic_code = _binding_value(row.get("topic_code"))
        topic_voc = _binding_value(row.get("topic_voc"))
        if topic_code is not None and topic_voc is not None:
            assertions.append(
                make_assertion(
                    self,
                    record,
                    legal_act,
                    "ABOUT_TOPIC",
                    topic_endpoint(topic_voc, topic_code),
                    valid_from=valid_from,
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
                make_assertion(
                    self,
                    record,
                    legal_act,
                    "APPLIES_TO",
                    topic_endpoint(applies_voc, applies_code),
                    valid_from=valid_from,
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
