# tests/unit/test_pipeline_run.py | v1.0.0 | introduced by WP-27
"""`execute_run` unit tests per Doc 2 §8.6.1 and §15.3.

The graph-touching paths are covered by the integration suite
(test_pipeline_run_structured / _unstructured); these tests pin the failure
surface with a fake driver and fake adapter: the budget contract, the
record-level skips, the configuration-failure abort, the no-assertions
cache-and-count path, and the reextract early return. The document path
runs the real spaCy gate, so a document that passes the gate exercises the
whole pipeline down to the loader seam.
"""

from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest
import spacy  # type: ignore[import-untyped]

from limes.archive.store import ArchiveStore
from limes.config import Settings
from limes.errors import ExtractionError, SourceFetchError
from limes.extraction.base import ExtractionResult
from limes.ontology.registry import load_ontology
from limes.pipeline.gate import GateContext
from limes.pipeline.run import RunSpec, execute_run
from limes.resolution.resolve import RunContext
from limes.sources.base import SourceAdapter, deterministic_assertion_id
from limes.types import (
    Assertion,
    EntityEndpoint,
    ExtractedAssertion,
    Mention,
    NormalizedRecord,
    Provenance,
    RawRecord,
    Validity,
)

REPO_ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]
ONTOLOGY = load_ontology(REPO_ROOT / "ontology" / "ontology.yaml")

LEI = "ABCDEFGHIJ0123456789"
OTHER_LEI = "9876543210ABCDEFGHIJ"

# A document the real German spaCy model gates in (the gate counts two
# entity mentions in the first sentence).
GATED_DOC_BODY = "Angela Merkel traf sich in Berlin mit der Bundesregierung."


def _settings(tmp_path, **overrides) -> Settings:
    base = dict(
        neo4j_uri="bolt://localhost:7687",
        neo4j_user="u",
        neo4j_password="p",
        ontology_path=REPO_ROOT / "ontology" / "ontology.yaml",
        feeds_config_path=REPO_ROOT / "ontology" / "feeds.yaml",
        gold_set_path=tmp_path / "gold_set.jsonl",
        baseline_path=tmp_path / "baseline.json",
        archive_path=tmp_path / "archive",
        openrouter_api_key="sk-test",
        embedding_model="test/embed",
        adjudication_model="test/adjudicator",
        extraction_model="test/extractor",
        extraction_prompt_version="1.0.0",
        extraction_schema_version="1.0.0",
        gate_min_entity_mentions=2,
        extraction_passage_window_sentences=3,
    )
    base.update(overrides)
    return Settings(**base)


class FakeCounters:
    nodes_created = 1
    relationships_created = 1
    properties_set = 0


class FakeTx:
    def __init__(self) -> None:
        self.ran: list[tuple[str, dict]] = []
        self.commit_called = False

    def run(self, cypher: str, **params):
        self.ran.append((cypher, params))
        return FakeResult()

    def commit(self) -> None:
        self.commit_called = True

    def rollback(self) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeResult:
    def __iter__(self):
        return iter([])

    def consume(self) -> SimpleNamespace:
        return SimpleNamespace(counters=FakeCounters())


class FakeRawDriver:
    def __init__(self) -> None:
        self._session = FakeSession()
        self.session_opens = 0

    @contextmanager
    def session(self, **kwargs):
        self.session_opens += 1
        yield self._session


class FakeSession:
    def __init__(self) -> None:
        self.tx = FakeTx()

    def begin_transaction(self) -> FakeTx:
        return self.tx


class FakeDriver:
    """Serves rows per read shape; records writes; carries the raw session
    seam the loader's transactions run on."""

    def __init__(
        self, source_rows: list[dict] | None = None, prior_rows: list[dict] | None = None
    ) -> None:
        self._source_rows = source_rows
        self._prior_rows = prior_rows or []
        self.writes: list[tuple[str, dict]] = []
        self.reads: list[str] = []
        self._driver = FakeRawDriver()

    def read(self, cypher: str, params: dict[str, Any], timeout_s: int) -> list[dict]:
        self.reads.append(cypher)
        if "cache_key" in params:
            return [{"exists": False}]
        if "content_hash" in params:
            return self._prior_rows
        if "source_id" in params:
            return self._source_rows or []
        return []

    def write_batch(self, statements: list[tuple[str, dict]]) -> None:
        self.writes.extend(statements)


def _source_row(last_success_at=None, last_run_id="run-0") -> dict:
    return {
        "source_id": "test",
        "name": "Test Source",
        "kind": "unstructured",
        "trust_rank": 0.8,
        "last_success_at": last_success_at,
        "last_run_id": last_run_id,
    }


def _raw_record(payload: bytes = b"raw") -> RawRecord:
    return RawRecord(payload=payload, content_type="text/plain", fetched_at=datetime.now(UTC))


class FakeAdapter(SourceAdapter):
    """A protocol-shaped adapter whose normalize is swapped per test."""

    source_id = "test"
    name = "Test Source"
    kind = "unstructured"
    trust_rank = 0.8
    supports_backfill = True
    supports_incremental = False

    def __init__(self, records: list[RawRecord] | None = None, normalize=None) -> None:
        self._records = records or []
        self.normalize = normalize
        self.fetch_calls = 0

    def fetch(self, since, until):
        self.fetch_calls += 1
        yield from self._records


class FakeRegistry:
    """Serves the adapter and its trust rank; anything else raises."""

    def __init__(self, adapter: FakeAdapter) -> None:
        self._adapter = adapter

    def get(self, source_id: str):
        if source_id == self._adapter.source_id:
            return self._adapter
        raise SourceFetchError(f"unknown source '{source_id}'")

    def trust_rank(self, source_id: str) -> float:
        return self.get(source_id).trust_rank


class FakeClient:
    """Canned embed vectors; resolution in these tests never reaches the
    paid bands, but the loader's embedding stamp does."""

    def embed(self, texts: list[str], model_id: str) -> list[list[float]]:
        return [[1.0] + [0.0] * 1023 for _ in texts]

    def complete(self, messages, model_id, purpose, json_schema=None):
        raise AssertionError("no completion call expected")


class FakeExtractor:
    model_id = "test/extractor"

    def __init__(
        self,
        assertions: list[ExtractedAssertion] | None = None,
        parse_errors: list[str] | None = None,
    ) -> None:
        self._assertions = assertions or []
        self._parse_errors = parse_errors or []
        self.calls = 0

    def extract(self, passages, ontology, prompt_version, schema_version) -> ExtractionResult:
        self.calls += 1
        return ExtractionResult(
            assertions=self._assertions,
            input_tokens=10,
            output_tokens=5,
            raw_response="[]",
            parse_errors=self._parse_errors,
        )


def _mention(surface: str, type_: str = "Corporation") -> Mention:
    return Mention(surface=surface, type=type_)


def _extracted(
    relation: str = "SUBSIDIARY_OF",
    subject: Mention | None = None,
    object_: Mention | None = None,
) -> ExtractedAssertion:
    return ExtractedAssertion(
        passage_index=0,
        subject=subject if subject is not None else _mention(LEI),
        relation=relation,
        object=object_ if object_ is not None else _mention(OTHER_LEI),
        valid_from=datetime(2024, 1, 1, tzinfo=UTC),
        confidence=0.9,
        evidence_start=0,
        evidence_end=20,
    )


def _structured_record(assertions=None) -> NormalizedRecord:
    return NormalizedRecord(
        content_hash="",
        kind="structured",
        assertions=assertions or [],
    )


def _resolved_assertion(relation: str = "SUBSIDIARY_OF") -> Assertion:
    return Assertion(
        assertion_id="a1",
        subject=EntityEndpoint(entity_id="e1", type="Corporation", label="E1"),
        relation=relation,
        object=EntityEndpoint(entity_id="e2", type="Corporation", label="E2"),
        validity=Validity(
            valid_from=datetime(2024, 1, 1, tzinfo=UTC), recorded_at=datetime.now(UTC)
        ),
        provenance=Provenance(
            source_id="s1", source_trust=0.8, confidence=0.9, ontology_version="1.0.0"
        ),
    )


def _document_record() -> NormalizedRecord:
    from limes.types import DocumentPayload

    return NormalizedRecord(
        content_hash="",
        kind="document",
        document=DocumentPayload(
            content_hash="doc-1",
            title="Test",
            body=GATED_DOC_BODY,
            language="de",
            published_at=datetime(2026, 7, 1, tzinfo=UTC),
        ),
    )


def _ctx(
    tmp_path, driver, adapter, *, client=None, extractor=None, gate=None, **settings_overrides
) -> RunContext:
    return RunContext(
        settings=_settings(tmp_path, **settings_overrides),
        ontology=ONTOLOGY,
        driver=driver,
        registry=FakeRegistry(adapter),
        archive=ArchiveStore(tmp_path / "archive"),
        client=client,
        extractor=extractor,
        gate=gate,
    )


def _gate(driver: FakeDriver, tmp_path) -> GateContext:
    return GateContext(
        settings=_settings(tmp_path),
        driver=driver,
        nlp_de=spacy.load("de_core_news_md"),
        nlp_en=spacy.load("en_core_web_md"),
    )


def test_document_kind_without_payload_is_counted_and_skipped(tmp_path):
    adapter = FakeAdapter(records=[_raw_record()])
    adapter.normalize = lambda record: NormalizedRecord(
        content_hash="", kind="document", document=None
    )
    driver = FakeDriver()
    ctx = _ctx(tmp_path, driver, adapter)
    record = execute_run(RunSpec(source_id="test", mode="ingest"), ctx)
    assert record.errors == 1
    assert record.records_fetched == 1


def test_structured_record_fully_rejected_is_counted_not_loaded(tmp_path):
    # A structured record whose assertions all fail validation contributes
    # nothing to the graph; the rejections are counted and the record ends
    # the path with a log, never a load call.
    bad = _structured_record(assertions=[_resolved_assertion(relation="NOT_A_RELATION")])
    adapter = FakeAdapter(records=[_raw_record()], normalize=lambda record: bad)
    driver = FakeDriver()
    ctx = _ctx(tmp_path, driver, adapter)
    record = execute_run(RunSpec(source_id="test", mode="ingest"), ctx)
    assert record.assertions_rejected == 1
    assert record.assertions_written == 0
    assert record.errors == 1
    assert record.state == "failed"
    assert not any("last_success_at" in params for _, params in driver.writes)
    # No loader statement reached the transaction.
    assert driver._driver._session.tx.ran == []


@pytest.mark.parametrize("rejected_by", ["ontology", "loader"])
def test_structured_rejection_has_no_checkpoint_or_load_receipt(tmp_path, monkeypatch, rejected_by):
    from limes.graph.loader import LoadResult
    from limes.sources.acquisition import AcquisitionStore

    raw = _raw_record()
    assertion = _resolved_assertion(
        relation="NOT_A_RELATION" if rejected_by == "ontology" else "OWNS")
    adapter = FakeAdapter(records=[raw], normalize=lambda _: _structured_record([assertion]))
    driver = FakeDriver()
    ctx = _ctx(tmp_path, driver, adapter)
    from dataclasses import replace

    ctx = replace(ctx, acquisitions=AcquisitionStore(ctx.archive, tmp_path / "progress"))
    if rejected_by == "loader":
        monkeypatch.setattr("limes.pipeline.run.load", lambda *a, **kw: LoadResult(rejected=1))
    record = execute_run(RunSpec(source_id="test", mode="ingest"), ctx)
    assert record.errors == record.assertions_rejected == 1
    assert record.state == "failed"
    assert not any("last_success_at" in params for _, params in driver.writes)
    import sqlite3

    database = next((tmp_path / "progress").rglob("progress.sqlite3"))
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT count(*) FROM loaded").fetchone()[0] == 0
        assert connection.execute("SELECT count(*) FROM state").fetchone()[0] > 0


def test_document_record_without_inference_aborts_the_run(tmp_path):
    adapter = FakeAdapter(records=[_raw_record()], normalize=lambda record: _document_record())
    driver = FakeDriver()
    ctx = _ctx(tmp_path, driver, adapter)  # no client, extractor, or gate
    with pytest.raises(ExtractionError, match="without inference"):
        execute_run(RunSpec(source_id="test", mode="ingest"), ctx)


def test_document_with_rejected_extraction_is_retryable_and_counted(tmp_path):
    # A document that passes the gate but yields only parse errors: nothing
    # reaches the graph. The partial failure stays retryable and cannot
    # advance the checkpoint or create a success cache marker.
    rejections = [
        "ONTOLOGY_REJECTED: item 0: Country -[ACTOR_IN]-> Event",
        "EVIDENCE_SPAN_MISMATCH: item 1: span 547:631 outside passage 0",
        "ONTOLOGY_REJECTED: item 2: Country -[TARGET_OF]-> Event",
    ]
    extractor = FakeExtractor(parse_errors=rejections)
    adapter = FakeAdapter(records=[_raw_record()], normalize=lambda record: _document_record())
    driver = FakeDriver()
    ctx = _ctx(
        tmp_path,
        driver,
        adapter,
        client=FakeClient(),
        extractor=extractor,
        gate=_gate(driver, tmp_path),
    )
    record = execute_run(RunSpec(source_id="test", mode="ingest"), ctx)
    assert record.assertions_rejected == 3
    assert record.errors == 3
    assert record.documents_gated_out == 1
    assert not any("ExtractionCacheEntry" in cypher for cypher, _ in driver.writes)
    assert extractor.calls == 1
    import json

    snapshots = [json.loads(ctx.archive.get(path.name))
                 for path in (tmp_path / "archive").rglob("*")
                 if path.is_file()
                 if ctx.archive.get(path.name).startswith(b"{")]
    diagnostic = next(item for item in snapshots if "parse_errors" in item)
    assert diagnostic["parse_errors"] == rejections
    assert diagnostic["raw_response"] == "[]"
    assert diagnostic["model_id"] == "test/extractor"
    assert diagnostic["response_truncated"] is False


def test_document_validation_rejection_is_counted(tmp_path):
    # An extracted assertion that fails ontology validation after resolution
    # lands in assertions_rejected; the empty load is a no-op.
    extractor = FakeExtractor(assertions=[_extracted(relation="NOT_A_RELATION")])
    adapter = FakeAdapter(records=[_raw_record()], normalize=lambda record: _document_record())
    driver = FakeDriver()
    ctx = _ctx(
        tmp_path,
        driver,
        adapter,
        client=FakeClient(),
        extractor=extractor,
        gate=_gate(driver, tmp_path),
    )
    record = execute_run(RunSpec(source_id="test", mode="ingest"), ctx)
    assert record.assertions_rejected == 1
    assert record.assertions_written == 0
    # A validation failure must stay retryable rather than poisoning the cache.
    assert not any("ExtractionCacheEntry" in cypher for cypher, _ in driver.writes)


def test_reextract_with_nothing_superseded_retracts_nothing(tmp_path):
    # The reextract path reads the prior assertions for the document; when
    # the new extraction reproduces all of them, nothing is retracted.
    item = _extracted()
    extractor = FakeExtractor(assertions=[item])
    adapter = FakeAdapter(records=[_raw_record()], normalize=lambda record: _document_record())
    prior_id = deterministic_assertion_id(
        "test",
        item.relation,
        f"lei:{LEI}",
        f"lei:{OTHER_LEI}",
        item.valid_from,
        None,
    )
    driver = FakeDriver(prior_rows=[{"assertion_id": prior_id}])
    ctx = _ctx(
        tmp_path,
        driver,
        adapter,
        client=FakeClient(),
        extractor=extractor,
        gate=_gate(driver, tmp_path),
    )
    record = execute_run(RunSpec(source_id="test", mode="reextract", budget_eur=Decimal("5")), ctx)
    assert record.assertions_written > 0
    # No retraction statement reached the raw session.
    assert not any("retracted_at" in cypher for cypher, _ in driver._driver._session.tx.ran)


def test_document_trust_falls_back_to_the_registry_value(tmp_path):
    # The adapter exposes no per-URL trust override, so the run falls back
    # to the registry's trust rank — stamped on every resolved assertion.
    extractor = FakeExtractor(assertions=[_extracted()])
    adapter = FakeAdapter(records=[_raw_record()], normalize=lambda record: _document_record())
    driver = FakeDriver()
    ctx = _ctx(
        tmp_path,
        driver,
        adapter,
        client=FakeClient(),
        extractor=extractor,
        gate=_gate(driver, tmp_path),
    )
    execute_run(RunSpec(source_id="test", mode="ingest"), ctx)
    loaded = [params for cypher, params in driver._driver._session.tx.ran if "props" in params]
    assert loaded
    assert loaded[0]["props"]["source_trust"] == 0.8


def test_source_without_a_read_row_still_runs(tmp_path):
    # `_read_source` returns None for a never-run source; the window falls
    # back to the adapter's own windowing, and the run proceeds.
    adapter = FakeAdapter(records=[_raw_record()], normalize=lambda record: _structured_record())
    driver = FakeDriver(source_rows=[])
    ctx = _ctx(tmp_path, driver, adapter)
    record = execute_run(RunSpec(source_id="test", mode="ingest"), ctx)
    assert record.records_fetched == 1
    assert adapter.fetch_calls == 1


def test_unexpected_datetime_from_the_driver_fails_loudly(tmp_path):
    # A last_success_at the driver cannot convert to a native datetime is a
    # programming error and raises rather than silently nulling the mark.
    adapter = FakeAdapter(records=[_raw_record()], normalize=lambda record: _structured_record())
    driver = FakeDriver(source_rows=[_source_row(last_success_at="2026-01-01")])
    ctx = _ctx(tmp_path, driver, adapter)
    with pytest.raises(TypeError, match="unexpected datetime value"):
        execute_run(RunSpec(source_id="test", mode="ingest"), ctx)


def test_partial_normalization_does_not_advance_source_checkpoint(tmp_path):
    normalized = _structured_record()
    normalized.errors = 1
    adapter = FakeAdapter(records=[_raw_record()], normalize=lambda raw: normalized)
    driver = FakeDriver()
    record = execute_run(RunSpec(source_id="test", mode="ingest"), _ctx(tmp_path, driver, adapter))
    assert record.errors == 1
    assert not any("last_success_at" in params for _, params in driver.writes)


def test_explicit_historical_window_checkpoint_uses_until(tmp_path):
    adapter = FakeAdapter(records=[_raw_record()], normalize=lambda raw: _structured_record())
    driver = FakeDriver()
    until = datetime(2026, 1, 2, tzinfo=UTC)
    execute_run(
        RunSpec(
            source_id="test", mode="backfill", since=datetime(2026, 1, 1, tzinfo=UTC), until=until
        ),
        _ctx(tmp_path, driver, adapter),
    )
    assert [p["last_success_at"] for _, p in driver.writes if "last_success_at" in p] == [until]


def test_fetch_response_parse_error_closes_run_without_checkpoint(tmp_path):
    from limes.errors import SourceParseError

    class BrokenSearchAdapter(FakeAdapter):
        def fetch(self, since, until):
            raise SourceParseError("invalid search response")
            yield  # generator-shaped fetch

    driver = FakeDriver()
    ctx = _ctx(tmp_path, driver, BrokenSearchAdapter())
    with pytest.raises(SourceParseError, match="invalid search response"):
        execute_run(RunSpec(source_id="test", mode="ingest"), ctx)
    closures = [params for _, params in driver.writes if "finished_at" in params]
    assert len(closures) == 1
    assert closures[0]["errors"] == 1
    assert not any("last_success_at" in params for _, params in driver.writes)


@pytest.mark.parametrize('retirement_fails', [False, True])
def test_acquisition_retirement_precedes_checkpoint_and_failure_is_durable(
    tmp_path, retirement_fails,
):
    driver = FakeDriver()
    adapter = FakeAdapter()
    retirements = []

    def complete_fetch():
        assert not any('last_success_at' in params for _, params in driver.writes)
        retirements.append(True)
        if retirement_fails:
            raise OSError('cursor retirement failed')

    adapter.complete_fetch = complete_fetch
    ctx = _ctx(tmp_path, driver, adapter)
    spec = RunSpec(source_id='test', mode='ingest')
    if retirement_fails:
        with pytest.raises(OSError, match='retirement failed'):
            execute_run(spec, ctx)
        assert not any('last_success_at' in params for _, params in driver.writes)
        assert any(params.get('errors') == 1 for _, params in driver.writes)
    else:
        result = execute_run(spec, ctx)
        assert result.errors == 0
        assert any('last_success_at' in params for _, params in driver.writes)
    assert retirements == [True]


@pytest.mark.parametrize("entries,errors,advances", [(0, 0, False), (1, 0, True), (1, 1, False)])
def test_feeds_checkpoint_requires_entries_and_clean_processing(
    tmp_path, entries, errors, advances
):
    normalized = _structured_record()
    normalized.errors = errors
    adapter = FakeAdapter(records=[_raw_record()] * entries, normalize=lambda raw: normalized)
    adapter.source_id = "feeds"
    driver = FakeDriver()
    record = execute_run(RunSpec(source_id="feeds", mode="ingest"), _ctx(tmp_path, driver, adapter))
    stamps = [p["last_success_at"] for _, p in driver.writes if "last_success_at" in p]
    assert stamps == ([record.started_at] if advances else [])


def test_restart_reuses_downloads_and_loads_only_unfinished_records(tmp_path, monkeypatch):
    from dataclasses import replace

    import httpx
    import respx

    from limes.sources.acquisition import AcquisitionStore
    from limes.sources.base import fetch_bytes, now_utc

    calls = []
    adapter = FakeAdapter(normalize=lambda raw: (calls.append(raw.payload) or _structured_record()))

    def fetch(since, until):
        for name in ("one", "two"):
            url = f"https://example.test/{name}"
            yield RawRecord(payload=fetch_bytes(url), content_type="text/plain",
                            source_url=url, fetched_at=now_utc())

    monkeypatch.setattr(adapter, "fetch", fetch)
    driver = FakeDriver()
    ctx = _ctx(tmp_path, driver, adapter)
    ctx = replace(ctx, acquisitions=AcquisitionStore(ctx.archive, tmp_path / "progress"))
    spec = RunSpec(source_id="test", mode="ingest")
    with respx.mock:
        one = respx.get("https://example.test/one").respond(200, content=b"one")
        two = respx.get("https://example.test/two").mock(side_effect=[
            httpx.Response(403), httpx.Response(200, content=b"two")
        ])
        with pytest.raises(SourceFetchError):
            execute_run(spec, ctx)
        assert calls == [b"one"]
        assert not any("last_success_at" in params for _, params in driver.writes)
        result = execute_run(spec, ctx)
        assert not result.errors
        assert calls == [b"one", b"two"]
        assert one.call_count == 1 and two.call_count == 2
        assert any("last_success_at" in params for _, params in driver.writes)


def test_processing_error_has_no_durable_loaded_receipt(tmp_path):
    from dataclasses import replace

    from limes.sources.acquisition import AcquisitionStore

    calls = []
    raw = _raw_record()

    def normalize(record):
        calls.append(record.payload)
        result = _structured_record()
        result.errors = int(len(calls) == 1)
        return result

    adapter = FakeAdapter(records=[raw], normalize=normalize)
    driver = FakeDriver()
    ctx = _ctx(tmp_path, driver, adapter)
    ctx = replace(ctx, acquisitions=AcquisitionStore(ctx.archive, tmp_path / "progress"))
    spec = RunSpec(source_id="test", mode="ingest")
    assert execute_run(spec, ctx).errors == 1
    assert not any("last_success_at" in params for _, params in driver.writes)
    assert execute_run(spec, ctx).errors == 0
    assert calls == [raw.payload, raw.payload]


def test_relative_backfill_resubmission_keeps_original_window_and_inventory(tmp_path, monkeypatch):
    import json
    from dataclasses import replace

    from limes.sources.acquisition import AcquisitionStore

    windows = []

    def fetch(since, until):
        windows.append((since, until))
        yield _raw_record()
        if len(windows) == 1:
            raise SourceFetchError("interrupted")

    adapter = FakeAdapter(normalize=lambda _: _structured_record())
    monkeypatch.setattr(adapter, "fetch", fetch)
    driver = FakeDriver()
    ctx = _ctx(tmp_path, driver, adapter)
    ctx = replace(ctx, acquisitions=AcquisitionStore(ctx.archive, tmp_path / "progress"))
    original = datetime(2026, 8, 1, tzinfo=UTC)
    with pytest.raises(SourceFetchError):
        execute_run(RunSpec(source_id="test", mode="backfill", since=original,
                            relative_days=1), ctx)
    result = execute_run(RunSpec(source_id="test", mode="backfill",
                                 since=datetime(2026, 8, 2, tzinfo=UTC), relative_days=1), ctx)
    assert result.errors == 0 and result.window_from == original
    assert windows[0] == windows[1]
    success = next(params for _, params in driver.writes if "last_success_at" in params)
    manifest = json.loads(ctx.archive.get(success["acquisition_manifest_hash"]))
    assert manifest["counts"]["loaded"] == 1
    assert ctx.archive.exists(manifest["inventory_hash"])


@pytest.mark.parametrize("blocked", [False, True, "partial"])
def test_only_productive_wall_slices_continue_not_partial_or_rate_limited_work(
    tmp_path, monkeypatch, blocked
):
    from dataclasses import replace

    import httpx
    import respx

    from limes.errors import SourceRunBudgetExceeded, SourceSliceEnded
    from limes.sources.acquisition import AcquisitionStore, active_acquisition
    from limes.sources.base import fetch_bytes

    clock = [0.0]
    monkeypatch.setattr("limes.pipeline.run.time.monotonic", lambda: clock[0])
    calls = []
    windows = []

    def fetch(since, until):
        windows.append((since, until))
        yield _raw_record(b"one")
        if len(windows) == 1:
            if blocked == "partial":
                active_acquisition.get().incomplete_reason = "failed publisher"
            elif blocked:
                fetch_bytes("https://example.test/blocked")
            clock[0] = 1901.0
        yield _raw_record(b"two")

    adapter = FakeAdapter(normalize=lambda raw: (calls.append(raw.payload) or _structured_record()))
    monkeypatch.setattr(adapter, "fetch", fetch)
    driver = FakeDriver()
    ctx = _ctx(tmp_path, driver, adapter)
    ctx = replace(ctx, acquisitions=AcquisitionStore(ctx.archive, tmp_path / "progress"))

    def limited(request):
        clock[0] = 1901.0
        return httpx.Response(429, headers={"Retry-After": "60"})

    spec = RunSpec(source_id="test", mode="ingest")
    with respx.mock:
        respx.get("https://example.test/blocked").mock(side_effect=limited)
        with pytest.raises(SourceRunBudgetExceeded) as raised:
            execute_run(spec, ctx)
        assert isinstance(raised.value, SourceSliceEnded) == (not blocked)
        assert not any("last_success_at" in params for _, params in driver.writes)
        closed = [params for _, params in driver.writes if "finished_at" in params][-1]
        assert closed["errors"] == int(bool(blocked))
        assert closed["state"] == ("failed" if blocked else "continuing")
        if not blocked:
            assert execute_run(spec, ctx).errors == 0
            assert calls == [b"one", b"two"]


def test_osm_productive_request_slices_keep_acquired_leaves_and_retire_after_checkpoint(
    tmp_path, monkeypatch
):
    from dataclasses import replace

    from limes.errors import SourceSliceEnded
    from limes.sources import osm
    from limes.sources.acquisition import AcquisitionStore
    from limes.sources.osm_acquisition import OsmAcquisition

    monkeypatch.setattr(osm, "OVERPASS_QUERIES", ("first", "second"))
    monkeypatch.setattr(osm, "MAX_REQUESTS_PER_RUN", 1)
    monkeypatch.setattr(osm.time, "sleep", lambda _: None)
    calls = []
    monkeypatch.setattr(osm, "fetch_bytes_form", lambda url, body, **kwargs: (
        calls.append(body["data"]) or b'{"elements":[]}'
    ))
    archive = ArchiveStore(tmp_path / "archive")
    cursor = tmp_path / "osm-cursor"
    adapter = osm.OsmAdapter(OsmAcquisition(archive, cursor))
    driver = FakeDriver()
    ctx = _ctx(tmp_path, driver, adapter)
    ctx = replace(ctx, acquisitions=AcquisitionStore(archive, tmp_path / "progress"))
    spec = RunSpec(source_id="osm", mode="ingest")
    with pytest.raises(SourceSliceEnded):
        execute_run(spec, ctx)
    assert calls == ["first"]
    assert (cursor / "active.json").exists()
    complete = adapter.complete_fetch

    def finish():
        assert any("last_success_at" in params for _, params in driver.writes)
        complete()

    monkeypatch.setattr(adapter, "complete_fetch", finish)
    result = execute_run(spec, ctx)
    assert not result.errors and result.records_fetched == 2
    assert calls == ["first", "second"]
    assert not (cursor / "active.json").exists()


def test_unexpected_adapter_exception_closes_run_as_failed(tmp_path):
    def broken(raw):
        raise TypeError("adapter bug")

    driver = FakeDriver()
    ctx = _ctx(tmp_path, driver, FakeAdapter(records=[_raw_record()], normalize=broken))
    with pytest.raises(TypeError, match="adapter bug"):
        execute_run(RunSpec(source_id="test", mode="ingest"), ctx)
    closed = [params for _, params in driver.writes if "finished_at" in params][-1]
    assert closed["errors"] == 1 and closed["state"] == "failed"
    assert closed["last_error"] == "TypeError: adapter bug"
    assert not any("last_success_at" in params for _, params in driver.writes)


@pytest.mark.parametrize("write_fails", [False, True])
def test_ted_pending_batch_flushes_on_interruption_and_receipts_follow_commit(
    tmp_path, monkeypatch, write_fails
):
    from dataclasses import replace

    from limes.errors import GraphWriteError
    from limes.graph.loader import LoadResult
    from limes.sources.acquisition import AcquisitionStore

    adapter = FakeAdapter()
    adapter.source_id = "ted"
    adapter.kind = "structured"
    calls = []
    failed = False
    raws = [_raw_record(b"one"), _raw_record(b"two")]

    def normalize(raw):
        calls.append(raw.payload)
        return _structured_record([_resolved_assertion()])

    def fetch(since, until):
        nonlocal failed
        yield from raws
        if not failed:
            failed = True
            raise SourceFetchError("next package interrupted")

    batches = []

    def write(driver, assertions, ontology, **kwargs):
        batches.append([a.provenance.evidence_document_id for a in assertions])
        assert kwargs["bulk"]
        if write_fails and len(batches) == 1:
            raise GraphWriteError("batch transaction failed")
        return LoadResult(written=len(assertions))

    adapter.normalize = normalize
    monkeypatch.setattr(adapter, "fetch", fetch)
    monkeypatch.setattr("limes.pipeline.run.load", write)
    driver = FakeDriver()
    ctx = _ctx(tmp_path, driver, adapter)
    ctx = replace(ctx, acquisitions=AcquisitionStore(ctx.archive, tmp_path / "progress"))
    spec = RunSpec(source_id="ted", mode="ingest")
    with pytest.raises(GraphWriteError if write_fails else SourceFetchError):
        execute_run(spec, ctx)
    assert len(batches) == 1 and len(batches[0]) == 2
    assert len(set(batches[0])) == 2  # distinct per-notice archived evidence
    assert not any("last_success_at" in parameters for _, parameters in driver.writes)
    result = execute_run(spec, ctx)
    assert not result.errors
    assert calls == [b"one", b"two"] * (2 if write_fails else 1)
    assert len(batches) == (2 if write_fails else 1)


@pytest.mark.parametrize("explicit_until", [False, True])
def test_explicit_historical_cutoff_does_not_certify_current_initial_corpus(
    tmp_path, explicit_until
):
    adapter = FakeAdapter(records=[_raw_record()], normalize=lambda _: _structured_record())
    adapter.supports_incremental = True
    adapter.full_initial_load = True
    driver = FakeDriver()
    execute_run(RunSpec(source_id="test", mode="ingest",
                        until=datetime(2020, 1, 1, tzinfo=UTC) if explicit_until else None),
                _ctx(tmp_path, driver, adapter))
    checkpoints = [parameters for _, parameters in driver.writes
                   if "last_success_at" in parameters]
    assert len(checkpoints) == 1
    assert checkpoints[0]["corpus_complete"] is (not explicit_until)
