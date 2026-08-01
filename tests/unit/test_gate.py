# tests/unit/test_gate.py | v1.0.0 | introduced by WP-24
"""Gate unit tests per Doc 2 §8.6.3 (WP-24).

The acceptance: documents below the mention threshold are rejected with the
reason recorded (AC-11); a cache hit short-circuits at zero cost (AC-12
partial); passage offsets are correct relative to the document; German and
English spaCy models are loaded and used correctly; a document with zero
passages yields `GateDecision(passed=False, reason="below_mention_threshold")`
— never a silent drop.

The spaCy models are the real installed models (de_core_news_md,
en_core_web_md); the driver is a stub whose only role is the cache existence
check.
"""

from datetime import UTC, datetime

import spacy  # type: ignore[import-untyped]

from limes.config import Settings
from limes.pipeline.gate import GateContext, gate_document, select_passages
from limes.types import DocumentPayload, NerSpan


def _settings(**overrides) -> Settings:
    base = dict(
        neo4j_uri="bolt://localhost:7687",
        neo4j_user="limes",
        neo4j_password="pw",
        ontology_path="/tmp/ontology.yaml",
        feeds_config_path="/tmp/feeds.yaml",
        gold_set_path="/tmp/gold_set.jsonl",
        baseline_path="/tmp/baseline.json",
        archive_path="/tmp/archive",
        gate_min_entity_mentions=2,
        extraction_passage_window_sentences=1,
        extraction_prompt_version="1.0.0",
        extraction_schema_version="1.0.0",
        extraction_model="test/model",
    )
    base.update(overrides)
    return Settings(**base)


class _DriverStub:
    """A driver whose only role in the gate is the cache existence check."""

    def __init__(self, cached: bool = False) -> None:
        self._cached = cached
        self.reads = 0

    def read(self, cypher: str, params: dict, timeout_s: int) -> list[dict]:
        self.reads += 1
        return [{"exists": self._cached}]


class _NeverNlp:
    """A spaCy model that fails the test if it is ever invoked."""

    def __call__(self, text: str):
        raise AssertionError("spaCy model must not be loaded on a cache hit")


class _RecordingNlp:
    """Wraps a real spaCy model and counts invocations, so a test can assert
    which language model the gate selected."""

    def __init__(self, nlp) -> None:
        self._nlp = nlp
        self.calls = 0

    def __call__(self, text: str):
        self.calls += 1
        return self._nlp(text)


def _doc(language: str = "de", body: str | None = None) -> DocumentPayload:
    return DocumentPayload(
        content_hash="hash-1",
        title="Test",
        body=body
        if body is not None
        else "Angela Merkel traf sich in Berlin mit der Bundesregierung.",
        language=language,
        published_at=datetime(2026, 8, 1, tzinfo=UTC),
        url="https://example.com/1",
    )


def test_cache_hit_short_circuits_at_zero_cost():
    # AC-12 (partial): the cache check is the first and only step on a hit —
    # no spaCy model is touched, no passage is selected.
    ctx = GateContext(
        settings=_settings(),
        driver=_DriverStub(cached=True),
        nlp_de=_NeverNlp(),
        nlp_en=_NeverNlp(),
    )
    decision = gate_document(_doc(), ctx)
    assert decision.passed is False
    assert decision.reason == "cache_hit"
    assert decision.passages == []


def test_german_document_passes_with_real_de_model():
    nlp_de = _RecordingNlp(spacy.load("de_core_news_md"))
    nlp_en = _RecordingNlp(spacy.load("en_core_web_md"))
    ctx = GateContext(settings=_settings(), driver=_DriverStub(), nlp_de=nlp_de, nlp_en=nlp_en)
    decision = gate_document(_doc(language="de"), ctx)
    assert decision.passed is True
    assert decision.reason == "passed"
    assert nlp_de.calls == 1
    assert nlp_en.calls == 0


def test_english_document_passes_with_real_en_model():
    nlp_de = _RecordingNlp(spacy.load("de_core_news_md"))
    nlp_en = _RecordingNlp(spacy.load("en_core_web_md"))
    ctx = GateContext(settings=_settings(), driver=_DriverStub(), nlp_de=nlp_de, nlp_en=nlp_en)
    decision = gate_document(
        _doc(language="en", body="The European Commission proposed new sanctions against Russia."),
        ctx,
    )
    assert decision.passed is True
    assert nlp_en.calls == 1
    assert nlp_de.calls == 0


def test_below_mention_threshold_rejects_with_reason():
    # AC-11: a document whose text carries no recognizable entities yields
    # zero passages and a counted rejection — never a silent drop.
    ctx = GateContext(
        settings=_settings(),
        driver=_DriverStub(),
        nlp_de=spacy.load("de_core_news_md"),
        nlp_en=spacy.load("en_core_web_md"),
    )
    decision = gate_document(
        _doc(body="Der Bericht wurde am Dienstag veröffentlicht und am Mittwoch kommentiert."),
        ctx,
    )
    assert decision.passed is False
    assert decision.reason == "below_mention_threshold"
    assert decision.passages == []


def test_unsupported_language_is_rejected_with_reason():
    ctx = GateContext(
        settings=_settings(),
        driver=_DriverStub(),
        nlp_de=_NeverNlp(),
        nlp_en=_NeverNlp(),
    )
    decision = gate_document(_doc(language="fr"), ctx)
    assert decision.passed is False
    assert decision.reason == "unsupported_language"


def test_passage_offsets_are_correct_relative_to_document():
    text = (
        "Die Kommission hat am Montag ein Paket vorgeschlagen. "
        "Der Rat prüft den Vorschlag nun. Das Wetter bleibt wechselhaft."
    )
    entities = [
        NerSpan(text="Kommission", label="ORG", start=4, end=14),
        NerSpan(text="Rat", label="ORG", start=65, end=68),
    ]
    # window 0: the two centers yield two separate passages, each exactly the
    # document slice it claims to be.
    passages = select_passages(text, "de", entities, window_sentences=0, min_mentions=1)
    assert len(passages) == 2
    for passage in passages:
        assert text[passage.doc_start : passage.doc_end] == passage.text
    # window 1: the windows overlap and merge into one passage.
    merged = select_passages(text, "de", entities, window_sentences=1, min_mentions=1)
    assert len(merged) == 1
    assert text[merged[0].doc_start : merged[0].doc_end] == merged[0].text
    assert "wechselhaft" in merged[0].text


def test_select_passages_min_mentions_threshold():
    text = "Die Kommission tagt. Das Wetter bleibt wechselhaft."
    entities = [NerSpan(text="Kommission", label="ORG", start=4, end=14)]
    # min_mentions=2: no sentence has two mentions -> no passages.
    assert select_passages(text, "de", entities, window_sentences=1, min_mentions=2) == []
    # min_mentions=1: the first sentence qualifies.
    passages = select_passages(text, "de", entities, window_sentences=0, min_mentions=1)
    assert len(passages) == 1
    assert passages[0].text.startswith("Die Kommission")


def test_select_passages_empty_text():
    assert select_passages("", "de", [], window_sentences=1, min_mentions=2) == []


def test_gate_filters_date_and_number_labels_before_counting():
    # A document whose only spans are dates and numbers must be rejected: the
    # label filter (gate._NON_ENTITY_LABELS) runs before the mention count,
    # so numbers alone cannot drive a passage (AC-11).
    ctx = GateContext(
        settings=_settings(),
        driver=_DriverStub(),
        nlp_de=spacy.load("de_core_news_md"),
        nlp_en=spacy.load("en_core_web_md"),
    )
    decision = gate_document(
        _doc(
            language="en",
            body="On August 3, 2026, at 5 pm, 50 percent of the report was released on Monday.",
        ),
        ctx,
    )
    assert decision.passed is False
    assert decision.reason == "below_mention_threshold"
