# src/limes/sources/osm.py | v1.0.0 | introduced by WP-19
"""OpenStreetMap/Overpass adapter per Technical Specification §8.5.2 (source: `osm`).

Loads KRITIS-relevant critical-infrastructure assets (Doc 1 §5.2) inside the
German bounding box: `Asset` nodes keyed by OSM id, their operator as
`OPERATES` (Corporation -> Asset), the region the postal-code correspondence
resolves as `LOCATED_IN` (Asset -> AdministrativeRegion), and the matched
KRITIS sector as a shared `Topic` node.

Non-obvious choices, each load-bearing:

- The window is ignored: OSM is a live database, not an archive - every query
  observes the present state, so a full load is the only load and
  `supports_incremental` is False. The source publishes no fact dates, so the
  fetch instant is the only timestamp the adapter knows: every assertion's
  `valid_from` and `recorded_at` are `fetched_at`, never `datetime.now()`.
- The ontology's `Asset.osm_type` property cannot be stamped: the loader
  stamps no arbitrary properties, and the endpoint carries only the
  deterministic key. The node-versus-way distinction survives in the raw
  payload the archive retains, just not as a queryable property.
- The ontology has no Asset->Topic edge (`ABOUT_TOPIC`'s domain excludes
  `Asset`), so a sector is never asserted as a relationship. The association
  rides the shared Topic node instead: every element of one sector produces
  the same `topic:KRITIS:<sector>` endpoint, and the loader merges on
  `entity_id`. This is an ontology-gap reading, not a modeling preference.
- Region assignment is a lookup, never geometry: the roadmap's
  "coordinate-based region assignment" contradicts the design, which forbids
  point-in-polygon work. The postal-code correspondence (C-07) is the only
  path to a region; a miss or an absent lookup leaves it unassigned - counted
  and summarized once, never guessed from the coordinates.
- OSM operators are usually utilities and grid operators - companies - so
  `Corporation` is the representable end of `OPERATES`' domain. OSM assigns
  no operator identifier, so identity is a name digest under the `operator`
  namespace.
- `_KRITIS_SECTORS` is the single refresh point: the Overpass query is
  derived from it at import time, so extending the map extends the fetch.
  Classification takes the first matching sector in map order; an element
  matching none is skipped and counted - belt and braces, the query already
  limits to these tags.
- A `Location`'s `coordinate_hash` is identity, never geometry: the digest
  over the rounded coordinate pair is stable across runs so the loader can
  merge, while the archive payload retains the full precision.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Iterator
from datetime import datetime
from typing import Literal

import structlog

from limes.errors import SourceParseError
from limes.sources.base import (
    ONTOLOGY_VERSION,
    deterministic_assertion_id,
    fetch_bytes_post,
    hash_entity_id,
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

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# South, west, north, east (Doc 2 §8.5.2: "DE bbox").
GERMANY_BBOX = "47.27,5.87,55.06,15.04"

# The KRITIS sector taxonomy (Doc 1 §5.2) as OSM tag selectors:
# sector -> tag key -> values that mark an element as an asset of that sector.
# The refresh point for the whole adapter: the Overpass query below is derived
# from this map, so a sector added here is fetched, classified, and loaded.
_KRITIS_SECTORS: dict[str, dict[str, list[str]]] = {
    "Energie": {"power": ["substation", "plant", "generator"]},
    "Wasser": {"man_made": ["water_works", "storage_tank", "wastewater_plant"]},
    "Gesundheit": {"amenity": ["hospital"], "healthcare": ["hospital"]},
    "IT": {"man_made": ["data_center"], "telecom": ["data_center"]},
    "Transport": {"railway": ["station"], "aeroway": ["terminal"]},
}


def _overpass_query() -> str:
    """One query covering every selector in `_KRITIS_SECTORS` in map order,
    one clause per tag key, restricted to the German bbox.

    Derived from the map so the fetch cannot drift from the taxonomy: adding a
    sector or a value here extends the query on the next process start. Values
    for a key that appears in several sectors (e.g. `man_made` for Wasser and
    IT) are merged into one clause, so no sector's selector is lost.
    """
    merged: dict[str, list[str]] = {}
    for tag_map in _KRITIS_SECTORS.values():
        for tag_key, values in tag_map.items():
            merged.setdefault(tag_key, []).extend(values)
    clauses = [
        f'  nwr["{tag_key}"~"^({"|".join(re.escape(v) for v in values)})$"]({GERMANY_BBOX});'
        for tag_key, values in merged.items()
    ]
    return "[out:json][timeout:60];\n(\n" + "\n".join(clauses) + "\n);\nout center;\n"


OVERPASS_QUERY = _overpass_query()


class OsmAdapter:
    """OpenStreetMap via Overpass - KRITIS assets in the German bbox."""

    source_id: str = "osm"
    name: str = "OpenStreetMap"
    kind: Literal["structured", "unstructured"] = "structured"
    trust_rank: float = 0.75
    supports_backfill: bool = False
    supports_incremental: bool = False

    def fetch(self, since: datetime | None, until: datetime | None) -> Iterator[RawRecord]:
        """Query the Overpass API for KRITIS-relevant tags in the German bbox.

        The window is ignored: the query observes the present OSM state, so a
        full load is the only load and a window changes nothing (§8.6.2 -
        `supports_incremental` is False). One `RawRecord` per fetch, archived
        as the `application/json` payload.
        """
        fetched_at = now_utc()
        payload = fetch_bytes_post(OVERPASS_URL, {"data": OVERPASS_QUERY})
        logger.info(
            "osm payload fetched",
            bytes=len(payload),
            fetched_at=fetched_at.isoformat(),
        )
        yield RawRecord(
            payload=payload,
            content_type="application/json",
            source_url=OVERPASS_URL,
            fetched_at=fetched_at,
        )

    def normalize(
        self,
        record: RawRecord,
        *,
        postal_lookup: Callable[[str, str], str | None] | None = None,
    ) -> NormalizedRecord:
        """One Overpass response to assets, operators, regions, sector topics.

        `postal_lookup` resolves (country, postal code) to a NUTS code from
        graph-resident reference data (C-07); the caller passes it when the
        correspondence is available. A missing lookup or a miss means no
        `LOCATED_IN` - never guessed - counted and summarized once.
        """
        elements, malformed = _parse_elements(record)
        assertions: list[Assertion] = []
        standalone: list[EntityEndpoint] = []
        seen: set[str] = set()
        skipped = 0
        missing_regions = 0
        no_coordinates = 0

        for element in elements:
            raw_id = element.get("id")
            if raw_id is None:
                malformed += 1
                logger.warning("osm: element without id skipped", element=element)
                continue
            element_id = str(raw_id)
            tags = _string_tags(element)
            if tags is None:
                malformed += 1
                logger.warning(
                    "osm: element tags malformed; element skipped", element_id=element_id
                )
                continue
            sector = _classify(tags)
            if sector is None:
                skipped += 1
                logger.warning(
                    "osm: element matches no KRITIS sector; skipped", element_id=element_id
                )
                continue
            asset = EntityEndpoint(
                entity_id=key_entity_id(("osm_id", element_id)),
                type="Asset",
                label=tags.get("name") or f"OSM {element.get('type', '')} {element_id}",
                deterministic_key=("osm_id", element_id),
            )
            topic = _topic(sector)
            if topic.entity_id not in seen:
                standalone.append(topic)
                seen.add(topic.entity_id)
            coords = _coordinates(element)
            if coords is None:
                no_coordinates += 1
                logger.warning(
                    "osm: element without coordinates; location skipped", element_id=element_id
                )
            else:
                location = _location(coords)
                if location.entity_id not in seen:
                    standalone.append(location)
                    seen.add(location.entity_id)
            operator = tags.get("operator")
            if operator:
                assertions.append(self._assertion(record, _operator(operator), "OPERATES", asset))
            country = tags.get("addr:country")
            postcode = tags.get("addr:postcode")
            if country and postcode:
                nuts = postal_lookup(country, postcode) if postal_lookup is not None else None
                if not nuts:
                    missing_regions += 1
                else:
                    region = EntityEndpoint(
                        entity_id=key_entity_id(("nuts_code", nuts)),
                        type="AdministrativeRegion",
                        label=nuts,
                        deterministic_key=("nuts_code", nuts),
                    )
                    assertions.append(self._assertion(record, asset, "LOCATED_IN", region))
        if missing_regions:
            logger.info(
                "gisco correspondence missing for N addresses; region unassigned",
                addresses=missing_regions,
                source_id=self.source_id,
            )
        logger.info(
            "osm: payload normalized",
            elements=len(elements),
            assets=len(elements) - malformed - skipped,
            assertions=len(assertions),
            standalone_entities=len(standalone),
            skipped=skipped,
            malformed=malformed,
            no_coordinates=no_coordinates,
            missing_regions=missing_regions,
            source_id=self.source_id,
        )
        return NormalizedRecord(
            content_hash=payload_hash(record.payload),
            kind="structured",
            assertions=assertions,
            entities=standalone,
        )

    def _assertion(
        self,
        record: RawRecord,
        subject: EntityEndpoint,
        relation: str,
        object_: EntityEndpoint,
    ) -> Assertion:
        return Assertion(
            assertion_id=deterministic_assertion_id(
                self.source_id,
                relation,
                subject.entity_id,
                object_.entity_id,
                record.fetched_at,
            ),
            subject=subject,
            relation=relation,
            object=object_,
            validity=Validity(valid_from=record.fetched_at, recorded_at=record.fetched_at),
            provenance=Provenance(
                source_id=self.source_id,
                source_trust=self.trust_rank,
                confidence=1.0,
                ontology_version=ONTOLOGY_VERSION,
            ),
        )


def _parse_elements(record: RawRecord) -> tuple[list[dict[str, object]], int]:
    """The response's element list, or `SourceParseError` for a payload that
    is not an Overpass JSON object. Non-object elements are counted, never
    silently dropped."""
    try:
        data = json.loads(record.payload)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise SourceParseError(f"osm: payload is not JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise SourceParseError("osm: payload is not a JSON object")
    elements = data.get("elements")
    if not isinstance(elements, list):
        raise SourceParseError("osm: payload lacks an elements list")
    parsed: list[dict[str, object]] = []
    malformed = 0
    for element in elements:
        if isinstance(element, dict):
            parsed.append(element)
        else:
            malformed += 1
            logger.warning("osm: non-object element skipped", element=repr(element)[:120])
    return parsed, malformed


def _string_tags(element: dict[str, object]) -> dict[str, str] | None:
    """The element's tags coerced to strings, or None when the tags are
    missing or carry a non-string value - malformed for an Overpass payload,
    never silently ignored."""
    raw_tags = element.get("tags")
    if not isinstance(raw_tags, dict) or not all(
        isinstance(value, str) for value in raw_tags.values()
    ):
        return None
    return {str(key): str(value) for key, value in raw_tags.items()}


def _classify(tags: dict[str, str]) -> str | None:
    """The first sector whose tag selector matches; map order is the
    precedence order. None means the element is not a KRITIS asset."""
    for sector, tag_map in _KRITIS_SECTORS.items():
        for tag_key, values in tag_map.items():
            if tags.get(tag_key) in values:
                return sector
    return None


def _coordinates(element: dict[str, object]) -> tuple[float, float] | None:
    """Node coordinates, else the way's `center`, else None. `out center`
    gives ways their geometry without fetching every member node; the
    fixture uses the real response shape."""
    lat, lon = _numeric(element.get("lat")), _numeric(element.get("lon"))
    if lat is not None and lon is not None:
        return lat, lon
    center = element.get("center")
    if isinstance(center, dict):
        lat, lon = _numeric(center.get("lat")), _numeric(center.get("lon"))
        if lat is not None and lon is not None:
            return lat, lon
    return None


def _numeric(value: object) -> float | None:
    """A JSON number, never a boolean (a subclass of int in Python)."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _topic(sector: str) -> EntityEndpoint:
    """The KRITIS sector as a Topic under the shared multi-key identity
    convention: the vocabulary rides in the `entity_id`, the code is the
    deterministic key, the sector name is the label."""
    return EntityEndpoint(
        entity_id=f"topic:KRITIS:{sector.lower()}",
        type="Topic",
        label=sector,
        deterministic_key=("code", sector.lower()),
    )


def _operator(name: str) -> EntityEndpoint:
    """A Corporation whose identity is the operator name digest: OSM assigns
    no operator identifier, and the name is the only stable fact the tag
    carries."""
    return EntityEndpoint(
        entity_id=hash_entity_id("operator", name),
        type="Corporation",
        label=name,
    )


def _location(coords: tuple[float, float]) -> EntityEndpoint:
    """A Location whose identity is the rounded-coordinate digest: the hash
    is identity, stable across runs, never geometry."""
    lat, lon = coords
    coordinate_key = f"{lat:.5f},{lon:.5f}"
    digest = hashlib.sha256(coordinate_key.encode("utf-8")).hexdigest()
    return EntityEndpoint(
        entity_id=key_entity_id(("coordinate_hash", digest)),
        type="Location",
        label=f"{lat:.5f}, {lon:.5f}",
        deterministic_key=("coordinate_hash", digest),
    )
