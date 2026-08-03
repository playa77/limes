# tests/unit/test_normalize.py | v1.0.0 | introduced by WP-09
"""Normalizer utility tests per Doc 2 §8.6 (normalizer role).

Pins language detection (de/en stopword heuristic), timestamp normalization
(day-first European default, explicit formats, naive-to-UTC), and text
extraction from HTML and XML — the two markup forms every structured source
arrives in.
"""

from datetime import UTC, datetime

import pytest

from limes.pipeline.normalize import (
    detect_language,
    extract_text_from_html,
    extract_text_from_xml,
    normalize_timestamp,
)

GERMAN_TEXT = "Die Bundesregierung hat den Gesetzentwurf über den Haushalt beschlossen und die"
ENGLISH_TEXT = "The government has adopted the budget bill and the parliament will now debate"


def test_detect_language_german_and_english():
    assert detect_language(GERMAN_TEXT) == "de"
    assert detect_language(ENGLISH_TEXT) == "en"


def test_detect_language_tie_breaks_to_english():
    assert detect_language("die the und and ist is") == "en"


def test_detect_language_empty_text_defaults_to_english():
    assert detect_language("") == "en"


def test_normalize_timestamp_iso_string():
    parsed = normalize_timestamp("2024-03-15T10:30:00Z")
    assert parsed == datetime(2024, 3, 15, 10, 30, tzinfo=UTC)


def test_normalize_timestamp_day_first_dotted():
    assert normalize_timestamp("15.01.2024") == datetime(2024, 1, 15, tzinfo=UTC)


def test_normalize_timestamp_explicit_format_wins():
    assert normalize_timestamp("2024/31/12", source_format="%Y/%d/%m") == datetime(
        2024, 12, 31, tzinfo=UTC
    )


def test_normalize_timestamp_datetime_input_keeps_timezone():
    aware = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)
    assert normalize_timestamp(aware) is aware


def test_normalize_timestamp_naive_datetime_gets_utc():
    parsed = normalize_timestamp(datetime(2024, 1, 1, 12, 0))
    assert parsed == datetime(2024, 1, 1, 12, 0, tzinfo=UTC)


def test_normalize_timestamp_unparseable_raises_value_error():
    with pytest.raises(ValueError):
        normalize_timestamp("not a date")


def test_extract_text_from_html_strips_markup_and_scripts():
    html_text = (
        "<html><head><title>X</title></head><body>"
        "<h1>Title</h1><script>var x = 1;</script>"
        "<p>Visible   text.</p></body></html>"
    )
    assert extract_text_from_html(html_text) == "Title Visible text."


def test_extract_text_from_html_plain_text_passes_through():
    assert extract_text_from_html("no markup here") == "no markup here"


def test_extract_text_from_html_parse_error_returns_empty():
    # A dangling comment is not a document; the lenient parser refuses it
    # and the extractor returns the empty string, never an exception.
    assert extract_text_from_html("<!--") == ""


def test_extract_text_from_xml_selects_xpath():
    xml_text = "<root><a>one</a><a>two</a><b>skip</b></root>"
    assert extract_text_from_xml(xml_text, "//a") == "one two"


def test_extract_text_from_xml_malformed_raises():
    with pytest.raises(ValueError):
        extract_text_from_xml("<root><a></root>", "//a")


def test_extract_text_from_xml_invalid_xpath_raises():
    with pytest.raises(ValueError):
        extract_text_from_xml("<root/>", "//[")
