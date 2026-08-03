# tests/unit/test_pipeline_passages.py | v1.0.0 | introduced by WP-24
"""Passage windowing unit tests per Doc 2 §8.6.3.

The windowing happy path (merging of overlapping windows, offset-exact
slices) is covered by the gate tests and the integration suite; these tests
pin the empty-input guard — a document without sentences must yield no
passages, never a crash or a fabricated slice.
"""

from limes.pipeline.passages import split_sentences, window_passages


def test_split_sentences_returns_triples():
    sentences = split_sentences("Eins. Zwei Drei. Vier.")
    assert sentences[0] == (0, 5, "Eins.")
    assert sentences[1][2] == "Zwei Drei."
    assert sentences[-1][2] == "Vier."


def test_window_passages_empty_text_yields_no_passages():
    assert window_passages("", [], [], window_sentences=2) == []


def test_window_passages_merges_overlapping_windows():
    text = "Eins. Zwei Drei. Vier Fünf. Sechs."
    passages = window_passages(text, ["Eins.", "Zwei Drei.", "Vier Fünf.", "Sechs."], [0, 2], 1)
    assert len(passages) == 1
    assert text[passages[0].doc_start : passages[0].doc_end] == passages[0].text
