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
  deterministic key. Element type is part of the key (`node/123`,
  `way/123`, `relation/123`); numeric IDs alone collide across OSM types.
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

import json
import re
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager, nullcontext
from datetime import datetime
from decimal import Decimal
from typing import Literal

import structlog

from limes.errors import SourceFetchError, SourceParseError
from limes.sources.base import (
    coordinate_location,
    fetch_bytes_form,
    hash_entity_id,
    key_entity_id,
    make_assertion,
    now_utc,
    payload_hash,
    topic_endpoint,
)
from limes.sources.osm_acquisition import OsmAcquisition, PartitionEntry
from limes.types import (
    Assertion,
    EntityEndpoint,
    NormalizedRecord,
    RawRecord,
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


def _overpass_query(bbox: str = GERMANY_BBOX) -> str:
    """One bounded query covering every selector in map order,
    one clause per tag key, restricted to the supplied bbox.

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
        f'  nwr["{tag_key}"~"^({"|".join(re.escape(v) for v in values)})$"]({bbox});'
        for tag_key, values in merged.items()
    ]
    return "[out:json][timeout:25];\n(\n" + "\n".join(clauses) + "\n);\nout center;\n"


def _partition_queries() -> tuple[str, ...]:
    # 8 x 10 adjoining cells cover the exact original bbox. Decimal arithmetic
    # preserves common boundaries; Overpass may return a way in several cells.
    south, west, north, east = map(Decimal, GERMANY_BBOX.split(","))
    height, width = (north - south) / 8, (east - west) / 10
    return tuple(
        _overpass_query(",".join(str(v) for v in (
            south + row * height, west + col * width,
            south + (row + 1) * height, west + (col + 1) * width,
        )))
        for row in range(8) for col in range(10)
    )


OVERPASS_QUERIES = _partition_queries()
# Compatibility identifier for diagnostics; acquisition uses OVERPASS_QUERIES.
OVERPASS_QUERY = _overpass_query()


MAX_SPLIT_DEPTH = 3
MAX_REQUESTS_PER_RUN = 200


class OverpassCapacityError(SourceParseError):
    """Explicit server resource exhaustion; eligible for bounded subdivision."""


def _split_query(query: str) -> tuple[str, ...]:
    boxes = re.findall(r'\]\(([-\d.,]+)\);', query)
    if not boxes or len(set(boxes)) != 1:
        raise SourceFetchError("osm: cannot subdivide query with an invalid bbox")
    south, west, north, east = map(Decimal, boxes[0].split(","))
    lat, lon = (south + north) / 2, (west + east) / 2
    return tuple(query.replace(f"({boxes[0]});", "(" + ",".join(map(str, box)) + ");")
                 for box in ((south, west, lat, lon), (south, lon, lat, east),
                             (lat, west, north, lon), (lat, lon, north, east)))


def _leaf_queries(splits: list[str]) -> list[tuple[str, str]]:
    """Derive coverage from trusted roots; reject orphan/overdeep cursor entries."""
    pending = [(str(i), query) for i, query in enumerate(OVERPASS_QUERIES)]
    leaves: list[tuple[str, str]] = []
    remaining = set(splits)
    if len(remaining) != len(splits):
        raise SourceFetchError("osm: duplicate split in acquisition cursor")
    while pending:
        key, query = pending.pop(0)
        if key in remaining:
            if key.count("/") >= MAX_SPLIT_DEPTH:
                raise SourceFetchError("osm: acquisition split depth exceeds limit")
            remaining.remove(key)
            pending[0:0] = [(f"{key}/{i}", child)
                            for i, child in enumerate(_split_query(query))]
        else:
            leaves.append((key, query))
    if remaining:
        raise SourceFetchError("osm: acquisition cursor contains orphan splits")
    return leaves


class OsmAdapter:
    """OpenStreetMap via Overpass - KRITIS assets in the German bbox."""

    source_id: str = "osm"
    name: str = "OpenStreetMap"
    kind: Literal["structured", "unstructured"] = "structured"
    trust_rank: float = 0.75
    supports_backfill: bool = False
    supports_incremental: bool = False

    def __init__(self, acquisition: OsmAcquisition | None = None) -> None:
        self.acquisition = acquisition
        self._completed_acquisition: str | None = None
        self._run_scope_active = False

    @contextmanager
    def run_scope(self) -> Iterator[None]:
        """Keep the acquisition lock through graph loading and acknowledgement."""
        if self.acquisition is None:
            raise SourceFetchError("osm: durable acquisition store is not configured")
        with self.acquisition.locked():
            self._run_scope_active = True
            try:
                yield
            finally:
                self._run_scope_active = False

    def fetch(self, since: datetime | None, until: datetime | None) -> Iterator[RawRecord]:
        """Acquire every bounded partition before exposing records for loading.

        Cached partitions retain original bytes and fetch instants. This is a
        collection over an acquisition interval, not a single OSM snapshot.
        Complete replay is necessary after graph-load failure; the cursor tracks
        successful acquisition only and never implies successful loading.
        """
        store = self.acquisition
        if store is None:
            raise SourceFetchError("osm: durable acquisition store is not configured")
        self._completed_acquisition = None
        plan_hash = payload_hash(json.dumps([OVERPASS_URL, *OVERPASS_QUERIES]).encode())
        with nullcontext() if self._run_scope_active else store.locked():
            state = store.read(plan_hash)
            leaves = _leaf_queries(state.splits)
            if not set(state.partitions) <= {key for key, _ in leaves}:
                raise SourceFetchError("osm: acquisition cursor contains unknown partitions")
            requests = 0
            index = 0
            while index < len(leaves):
                partition, query = leaves[index]
                if partition in state.partitions:
                    _validated_elements(store.payload(state.partitions[partition]))
                    index += 1
                    continue
                if requests >= MAX_REQUESTS_PER_RUN:
                    raise SourceFetchError(
                        "osm: acquisition request limit reached; "
                        "progress retained for explicit resume")
                if requests:
                    time.sleep(1)
                requests += 1
                fetched_at = now_utc()
                payload = fetch_bytes_form(OVERPASS_URL, {"data": query})
                content_hash = store.archive.put("osm", payload, "application/json")
                try:
                    _validated_elements(payload)
                except OverpassCapacityError as exc:
                    if partition.count("/") >= MAX_SPLIT_DEPTH:
                        raise SourceFetchError(
                            f"osm: partition {partition} exhausted subdivision depth; "
                            "acquisition incomplete, progress retained") from exc
                    state.splits.append(partition)
                    store.write(state)  # durable topology before requesting children
                    leaves = _leaf_queries(state.splits)
                    logger.info("osm partition subdivided", partition=partition,
                                error_content_hash=content_hash, leaves=len(leaves))
                    continue
                state.partitions[partition] = PartitionEntry(
                    content_hash=content_hash, fetched_at=fetched_at)
                store.write(state)
                index += 1
                logger.info("osm partition acquired", partition=partition,
                            completed=len(state.partitions), total=len(leaves),
                            bytes=len(payload), content_hash=content_hash)
            if set(state.partitions) != {key for key, _ in leaves}:
                raise SourceFetchError("osm: partition coverage is incomplete")
            manifest_hash = store.manifest(state)
            seen: set[str] = set()
            for index, (partition, _) in enumerate(leaves):
                entry = state.partitions[partition]
                payload = store.payload(entry)
                excluded: list[str] = []
                for element in _validated_elements(payload):
                    key = _element_key(element)
                    if key in seen:
                        excluded.append(key)
                    else:
                        seen.add(key)
                yield RawRecord(
                    payload=payload, content_type="application/json", source_url=OVERPASS_URL,
                    fetched_at=entry.fetched_at,
                    acquisition_context={
                        "acquisition_id": state.acquisition_id, "plan_hash": plan_hash,
                        "partition": index, "partition_key": partition,
                        "partition_count": len(leaves),
                        "acquisition_manifest_hash": manifest_hash,
                        "excluded_elements": excluded,
                    },
                )
            self._completed_acquisition = state.acquisition_id

    def complete_fetch(self) -> None:
        """Retire state after complete loading, before the source success checkpoint."""
        if self.acquisition is not None and self._completed_acquisition is not None:
            self.acquisition.complete(
                self._completed_acquisition, already_locked=self._run_scope_active)
            self._completed_acquisition = None

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
        assets = 0
        duplicates = 0

        raw_excluded = (record.acquisition_context or {}).get("excluded_elements", [])
        excluded = set(raw_excluded) if isinstance(raw_excluded, list) else set()
        element_keys: set[str] = set()
        for element in elements:
            element_key = _element_key(element)
            if element_key in excluded or element_key in element_keys:
                duplicates += 1
                continue
            element_keys.add(element_key)
            raw_id = element.get("id")
            if raw_id is None:
                malformed += 1
                logger.warning("osm: element without id skipped", element=element)
                continue
            element_id = _element_key(element)
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
                label=tags.get("name") or f"OSM {element_id}",
                deterministic_key=("osm_id", element_id),
            )
            assets += 1
            standalone.append(asset)
            topic = topic_endpoint("KRITIS", sector.lower(), label=sector)
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
                lat, lon = coords
                location = coordinate_location(lat, lon)
                if location.entity_id not in seen:
                    standalone.append(location)
                    seen.add(location.entity_id)
            operator = tags.get("operator")
            if operator:
                assertions.append(
                    make_assertion(self, record, _operator(operator), "OPERATES", asset)
                )
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
                    assertions.append(make_assertion(self, record, asset, "LOCATED_IN", region))
        if missing_regions:
            logger.info(
                "gisco correspondence missing for N addresses; region unassigned",
                addresses=missing_regions,
                source_id=self.source_id,
            )
        logger.info(
            "osm: payload normalized",
            elements=len(elements),
            assets=assets,
            duplicates=duplicates,
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
    remark = data.get("remark")
    if isinstance(remark, str) and remark.startswith("runtime error:") and (
        "Query timed out" in remark or "out of memory" in remark
    ):
        raise OverpassCapacityError("osm: Overpass resource limit; incomplete response")
    if remark:
        raise SourceParseError("osm: Overpass returned an error remark; incomplete response")
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


def _element_key(element: dict[str, object]) -> str:
    return f"{element.get('type', 'unknown')}/{element.get('id')}"


def _validated_elements(payload: bytes) -> list[dict[str, object]]:
    record = RawRecord(payload=payload, content_type="application/json",
                       source_url=OVERPASS_URL, fetched_at=now_utc())
    elements, malformed = _parse_elements(record)
    keys: set[str] = set()
    for element in elements:
        raw_id = element.get("id")
        if (element.get("type") not in ("node", "way", "relation")
                or not isinstance(raw_id, int) or isinstance(raw_id, bool) or raw_id <= 0
                or _string_tags(element) is None or _element_key(element) in keys):
            malformed += 1
        keys.add(_element_key(element))
    if malformed:
        raise SourceParseError("osm: malformed partition elements; completeness unverified")
    return elements


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


def _operator(name: str) -> EntityEndpoint:
    """A Corporation whose identity is the operator name digest: OSM assigns
    no operator identifier, and the name is the only stable fact the tag
    carries."""
    return EntityEndpoint(
        entity_id=hash_entity_id("operator", name),
        type="Corporation",
        label=name,
    )


def _numeric(value: object) -> float | None:
    """A JSON number, never a boolean (a subclass of int in Python)."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None
