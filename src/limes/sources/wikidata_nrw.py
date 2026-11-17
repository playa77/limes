# src/limes/sources/wikidata_nrw.py | v1.0.0 | introduced by BE-59
"""NRW-headquartered companies and Vereine from Wikidata (source: `wikidata_nrw`).

BE-59 replaces nationwide registry dumps (OffeneRegister) with selection at the
source: one bounded SPARQL query asks the Wikidata Query Service for items of a
closed set of organisation classes whose headquarters (P159) is located (P131*)
in Nordrhein-Westfalen (`geo_scope.WIKIDATA_QID`). Nothing outside NRW is
downloaded.

Mapping choices, each load-bearing:
- Type is decided per item, never per row: an item listed under a company class
  is a `Corporation`, otherwise an `InterestGroup` (associations, nonprofits,
  foundations). One item therefore never forks into two typed nodes.
- A company with a Wikidata LEI (P1278) keys on `lei`, so it merges with the GLEIF
  node; otherwise it keys on `wikidata_qid`. `InterestGroup` declares no QID key
  in the ontology, so a Verein carries a stable QID-derived `entity_id` without a
  deterministic key — no ontology change, no name-based identity.
- The headquarters becomes a `Location` keyed by its coordinate digest when the
  HQ item has coordinates (P625); without them only the organisation is emitted.
- The query is one snapshot; the window is ignored and every assertion is valid
  from the fetch instant. A result at the row bound fails loudly rather than
  silently truncating.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from datetime import datetime
from typing import Any, Literal
from urllib.parse import urlencode

import structlog

from limes.errors import SourceParseError
from limes.geo_scope import WIKIDATA_QID as NRW_QID
from limes.sources.base import (
    coordinate_location,
    fetch_bytes,
    hash_entity_id,
    key_entity_id,
    make_assertion,
    now_utc,
    payload_hash,
)
from limes.types import EntityEndpoint, NormalizedRecord, RawRecord

logger = structlog.get_logger(__name__)

SPARQL_URL = "https://query.wikidata.org/sparql"
CONTENT_TYPE = "application/sparql-results+json"
MAX_ROWS = 20_000
MAX_BYTES = 64 * 1024 * 1024

# Closed class map (P31 values). Company classes win over association classes.
COMPANY_CLASSES = ("Q4830453", "Q6881511")  # business, enterprise
ASSOCIATION_CLASSES = ("Q48204", "Q163740", "Q157031")  # voluntary assoc., nonprofit, foundation

_QID = re.compile(r"^Q[1-9][0-9]*$")
_LEI = re.compile(r"^[A-Z0-9]{18}[0-9]{2}$")
_POINT = re.compile(r"^Point\((-?[0-9.]+) (-?[0-9.]+)\)$")


def build_query() -> str:
    classes = " ".join(f"wd:{q}" for q in (*COMPANY_CLASSES, *ASSOCIATION_CLASSES))
    return (
        "SELECT ?o ?oLabel ?c ?lei ?hq ?hqLabel ?coord WHERE { "
        f"VALUES ?c {{ {classes} }} "
        f"?o wdt:P31 ?c ; wdt:P159 ?hq . ?hq wdt:P131* wd:{NRW_QID} . "
        "OPTIONAL { ?o wdt:P1278 ?lei } OPTIONAL { ?hq wdt:P625 ?coord } "
        'SERVICE wikibase:label { bd:serviceParam wikibase:language "de,en". } '
        f"}} LIMIT {MAX_ROWS + 1}"
    )


def _qid(uri: str) -> str:
    qid = uri.rsplit("/", 1)[-1]
    if not _QID.match(qid):
        raise SourceParseError(f"wikidata_nrw: malformed entity URI {uri!r}")
    return qid


def _value(row: dict[str, Any], name: str) -> str | None:
    cell = row.get(name)
    return str(cell["value"]) if isinstance(cell, dict) and "value" in cell else None


class WikidataNrwAdapter:
    """Wikidata — organisations headquartered in Nordrhein-Westfalen."""

    source_id: str = "wikidata_nrw"
    name: str = "Wikidata NRW organisations"
    kind: Literal["structured", "unstructured"] = "structured"
    trust_rank: float = 0.90
    supports_backfill: bool = False
    supports_incremental: bool = False

    def fetch(self, since: datetime | None, until: datetime | None) -> Iterator[RawRecord]:
        url = f"{SPARQL_URL}?{urlencode({'query': build_query(), 'format': 'json'})}"
        payload = fetch_bytes(
            url, timeout_s=120, max_bytes=MAX_BYTES, headers={"Accept": CONTENT_TYPE}
        )
        yield RawRecord(
            payload=payload, content_type=CONTENT_TYPE, source_url=SPARQL_URL, fetched_at=now_utc()
        )

    def normalize(self, record: RawRecord) -> NormalizedRecord:
        try:
            rows = json.loads(record.payload)["results"]["bindings"]
        except (ValueError, KeyError, TypeError) as exc:
            raise SourceParseError(f"wikidata_nrw: malformed SPARQL response: {exc}") from exc
        if len(rows) > MAX_ROWS:
            raise SourceParseError("wikidata_nrw: result reached the row bound; not truncating")

        items: dict[str, dict[str, Any]] = {}
        for row in rows:
            qid = _qid(_value(row, "o") or "")
            item = items.setdefault(qid, {"classes": set(), "hq": {}, "lei": None})
            item["label"] = _value(row, "oLabel") or qid
            item["classes"].add(_qid(_value(row, "c") or ""))
            lei = _value(row, "lei")
            if lei and _LEI.match(lei):
                item["lei"] = lei
            hq, coord = _value(row, "hq"), _value(row, "coord")
            if hq and coord:
                item["hq"][_qid(hq)] = (coord, _value(row, "hqLabel"))

        entities: list[EntityEndpoint] = []
        assertions = []
        skipped_coordinates = 0
        for qid in sorted(items):
            item = items[qid]
            org = self._organisation(qid, item)
            located = False
            for _hq_qid, (coord, hq_label) in sorted(item["hq"].items()):
                match = _POINT.match(coord)
                if match is None:
                    skipped_coordinates += 1
                    continue
                lon, lat = float(match[1]), float(match[2])
                place = coordinate_location(lat, lon, label=hq_label)
                assertions.append(make_assertion(self, record, org, "HEADQUARTERED_IN", place))
                located = True
            if not located:
                entities.append(org)
        logger.info(
            "wikidata_nrw normalized",
            organisations=len(items),
            assertions=len(assertions),
            skipped_coordinates=skipped_coordinates,
        )
        return NormalizedRecord(
            content_hash=payload_hash(record.payload),
            kind="structured",
            assertions=assertions,
            entities=entities,
            errors=skipped_coordinates,
        )

    @staticmethod
    def _organisation(qid: str, item: dict[str, Any]) -> EntityEndpoint:
        label = str(item["label"])
        if item["classes"] & set(COMPANY_CLASSES):
            key = ("lei", item["lei"]) if item["lei"] else ("wikidata_qid", qid)
            return EntityEndpoint(
                entity_id=key_entity_id(key), type="Corporation", label=label,
                deterministic_key=key,
            )
        return EntityEndpoint(
            entity_id=hash_entity_id("interest-group-wikidata", qid),
            type="InterestGroup",
            label=label,
            aliases=[qid],
        )
