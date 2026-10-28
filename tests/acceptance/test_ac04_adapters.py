# tests/acceptance/test_ac04_adapters.py | v1.0.0 | introduced by WP-39
"""AC-04: all thirteen adapters produce the expected record set from
recorded fixtures, with correct deterministic keys and source attribution.

The per-adapter exact record sets are asserted by the adapter unit suites
(WP-10…WP-21); this test proves the registry-level claim: every adapter
delivered into `build_default_registry()` normalizes its recorded fixtures
through the production `normalize` path with `source_id`/`source_trust`
stamped on every assertion and every declared deterministic key present.
Wikidata is enrichment-only (its `fetch` raises `NotImplementedError`).
No test touches the network.
"""

from __future__ import annotations

import gzip
import io
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from limes.ontology.registry import load_ontology
from limes.sources import (
    bundestag_dip,
    eurlex,
    feeds,
    fsd,
    gdelt,
    offeneregister,
    osm,
    transparency_register,
    wikidata,
)
from limes.sources.registry import build_default_registry
from limes.types import RawRecord

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "tests" / "fixtures"
ONTOLOGY_PATH = REPO_ROOT / "ontology" / "ontology.yaml"

FETCHED_AT = datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC)

EXPECTED_SOURCE_IDS = [
    "bundestag_dip",
    "eurlex",
    "feeds",
    "fsd",
    "gdelt",
    "gesetze_im_internet",
    "gisco_nuts",
    "gleif",
    "offeneregister",
    "osm",
    "ted",
    "transparency_register",
    "wikidata",
]


def _csv_record(path: str, content_type: str, url: str) -> RawRecord:
    return RawRecord(
        payload=(FIXTURES / path).read_bytes(),
        content_type=content_type,
        source_url=url,
        fetched_at=FETCHED_AT,
    )


def _zip_record(path: str, member: str, url: str) -> RawRecord:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(member, (FIXTURES / path).read_text(encoding="utf-8"))
    return RawRecord(
        payload=buffer.getvalue(),
        content_type="application/zip",
        source_url=url,
        fetched_at=FETCHED_AT,
    )


def _law_zip_record(path: str, member: str, url: str) -> RawRecord:
    return _zip_record(path, member, url)


def _records_for(source_id: str) -> list[RawRecord]:
    """The recorded fixtures of one adapter as raw records, wrapped exactly
    as `fetch` would deliver them (zip/gzip where the source ships zips)."""
    if source_id == "gisco_nuts":
        return [
            _csv_record(
                "gisco_nuts/nuts_hierarchy.csv",
                "text/csv",
                "https://example.test/nuts.csv",
            ),
            _csv_record(
                "gisco_nuts/postcode_correspondence.csv",
                "text/csv",
                "https://example.test/postcodes.csv",
            ),
        ]
    if source_id == "gleif":
        return [
            _zip_record("gleif/entities.csv", "entities.csv", "https://example.test/entities.zip"),
            _zip_record(
                "gleif/relationships.csv",
                "relationships.csv",
                "https://example.test/relationships.zip",
            ),
        ]
    if source_id == "eurlex":
        return [
            RawRecord(
                payload=(FIXTURES / "eurlex" / "sparql_results.json").read_bytes(),
                content_type="application/json",
                source_url=eurlex.SPARQL_URL,
                fetched_at=FETCHED_AT,
            )
        ]
    if source_id == "fsd":
        return [
            RawRecord(
                payload=(FIXTURES / "fsd" / "sanctions.xml").read_bytes(),
                content_type="application/xml",
                source_url=fsd.FSD_URL,
                fetched_at=FETCHED_AT,
            )
        ]
    if source_id == "ted":
        return [
            RawRecord(
                payload=(FIXTURES / "ted" / "award_lei.xml").read_bytes(),
                content_type="application/xml",
                source_url="https://ted.europa.eu/api/v3/notices/123456-2025/raw",
                fetched_at=FETCHED_AT,
            )
        ]
    if source_id == "transparency_register":
        return [
            RawRecord(
                payload=(FIXTURES / "transparency_register" / "export.xml").read_bytes(),
                content_type="application/xml",
                source_url=transparency_register.EXPORT_URL,
                fetched_at=FETCHED_AT,
            )
        ]
    if source_id == "bundestag_dip":
        return [
            RawRecord(
                payload=(FIXTURES / "bundestag_dip" / "persons.json").read_bytes(),
                content_type="application/json",
                source_url=bundestag_dip.PERSON_URL,
                fetched_at=FETCHED_AT,
            )
        ]
    if source_id == "gesetze_im_internet":
        # The TOC record is a fetch artifact, not a normalize input: the
        # adapter's `normalize` rejects non-law payloads with
        # `SourceParseError` by design, and the pipeline counts that as a
        # record-level error. Only the law zips normalize.
        return [
            _law_zip_record(
                "gesetze_im_internet/gesetz_mit_sachgebiet.xml",
                "BJNR204500000.xml",
                "https://example.test/law-with-topics.zip",
            ),
            _law_zip_record(
                "gesetze_im_internet/gesetz_ohne_sachgebiet.xml",
                "BJNR104200013.xml",
                "https://example.test/law-without-topics.zip",
            ),
        ]
    if source_id == "osm":
        return [
            RawRecord(
                payload=(FIXTURES / "osm" / "overpass_response.json").read_bytes(),
                content_type="application/json",
                source_url=osm.OVERPASS_URL,
                fetched_at=FETCHED_AT,
            )
        ]
    if source_id == "offeneregister":
        return [
            RawRecord(
                payload=(FIXTURES / "offeneregister" / "meta.json").read_bytes(),
                content_type="application/json",
                source_url=offeneregister.METADATA_URL,
                fetched_at=FETCHED_AT,
            ),
            RawRecord(
                payload=gzip.compress(
                    (FIXTURES / "offeneregister" / "companies.jsonl").read_bytes()
                ),
                content_type="application/gzip",
                source_url=offeneregister.DATA_URL,
                fetched_at=FETCHED_AT,
            ),
        ]
    if source_id == "gdelt":
        return [
            RawRecord(
                payload=_gdelt_zip(),
                content_type="application/zip",
                source_url=gdelt.FILE_URL_TEMPLATE.format(
                    slot=datetime(2026, 8, 1, 15, 45, tzinfo=UTC)
                ),
                fetched_at=FETCHED_AT,
            )
        ]
    if source_id == "feeds":
        return [
            RawRecord(
                payload=json.dumps(
                    {
                        "feed": {
                            "url": "https://example.com/rss",
                            "name": "Test",
                            "language": "en",
                        },
                        "entry_id": "entry-1",
                        "title": "Title",
                        "link": "https://example.com/1",
                        "summary": "",
                        "content": "<p>Body text.</p>",
                        "published": "2026-07-31T09:30:00+00:00",
                    },
                    sort_keys=True,
                ).encode("utf-8"),
                content_type=feeds.ENVELOPE_CONTENT_TYPE,
                source_url="https://example.com/rss",
                fetched_at=FETCHED_AT,
            )
        ]
    if source_id == "wikidata":
        return []  # enrichment-only: no fetch, no normalize-from-fetch
    raise AssertionError(f"no fixture mapping for adapter {source_id!r}")


def test_ac04_registry_returns_all_thirteen_adapters():
    registry = build_default_registry()
    assert registry.source_ids() == EXPECTED_SOURCE_IDS


def test_ac04_every_adapter_normalizes_fixtures_with_attribution():
    registry = build_default_registry()
    ontology = load_ontology(ONTOLOGY_PATH)
    for source_id in EXPECTED_SOURCE_IDS:
        adapter = registry.get(source_id)
        records = _records_for(source_id)
        if not records:
            continue
        normalized = [adapter.normalize(record) for record in records]
        assertions = [a for record in normalized for a in record.assertions]
        entities = [e for record in normalized for e in record.entities]
        for assertion in assertions:
            assert assertion.provenance.source_id == source_id, source_id
            assert assertion.provenance.source_trust == adapter.trust_rank, source_id
        for entity in entities:
            if entity.deterministic_key is None:
                continue
            key_name = entity.deterministic_key[0]
            assert key_name in ontology.entity_types[entity.type].identifying_keys, (
                source_id,
                entity.type,
                key_name,
            )


def test_ac04_fixture_records_produce_expected_deterministic_keys():
    """Spot checks that the deterministic key values themselves are the
    canonical ones the ontology constrains (the exact-record-set assertion
    lives in the per-adapter unit suites)."""
    registry = build_default_registry()

    gisco = registry.get("gisco_nuts")
    endpoints = [
        endpoint
        for record in gisco_fixture_records()
        for normalized in [gisco.normalize(record)]
        for endpoint in [a.subject for a in normalized.assertions]
        + [a.object for a in normalized.assertions]
        + normalized.entities
    ]
    assert any(endpoint.deterministic_key == ("nuts_code", "DE11") for endpoint in endpoints), (
        "the DE11 region must carry its canonical NUTS key"
    )

    gleif = registry.get("gleif")
    gleif_records = _records_for("gleif")
    gleif_assertions = [a for record in gleif_records for a in gleif.normalize(record).assertions]
    assert gleif_assertions, "GLEIF fixtures must produce assertions"
    for assertion in gleif_assertions:
        for endpoint in (assertion.subject, assertion.object):
            if endpoint.deterministic_key is None:
                continue
            # Corporation endpoints carry the canonical LEI; the location
            # endpoints of HEADQUARTERED_IN carry the address hash.
            if endpoint.type == "Corporation":
                assert endpoint.deterministic_key[0] == "lei", endpoint
            else:
                assert endpoint.deterministic_key[0] in ("coordinate_hash", "geonames_id"), endpoint


def gisco_fixture_records() -> list[RawRecord]:
    return _records_for("gisco_nuts")


def test_ac04_wikidata_is_enrichment_only():
    adapter = wikidata.WikidataAdapter()
    with pytest.raises(NotImplementedError):
        list(adapter.fetch(None, None))


def _gdelt_zip() -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("20260801154500.export.CSV", (FIXTURES / "gdelt/events.tsv").read_bytes())
    return stream.getvalue()
