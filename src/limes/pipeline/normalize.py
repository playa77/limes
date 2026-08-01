# src/limes/pipeline/normalize.py | v1.0.0 | introduced by WP-09
"""Shared normalization utilities per Technical Specification §8.6 and
Design Document §4.3: language detection, timestamp normalization, and text
extraction from markup. Every adapter calls these from its `normalize` method;
the definitions live here so the heuristics are one thing, not eleven copies.

The language detector is deliberately dependency-free: `langdetect` is not in
the dependency manifest (adding one is a human decision), and a stopword
count over German and English function words is accurate enough to decide
between the two languages this system accepts (Doc 1 §3.4). Timestamps
default to day-first parsing because every source in the table is European;
a caller with a known format passes it explicitly rather than fighting the
heuristic.
"""

from __future__ import annotations

from datetime import UTC, datetime

import structlog
from dateutil import parser as dateutil_parser  # type: ignore[import-untyped]
from lxml import etree, html  # type: ignore[import-untyped]

logger = structlog.get_logger(__name__)

_DE_STOPWORDS = frozenset(
    """
    der die das und ist nicht mit für auf von eine ein den dem im in zu sind
    wird wurde werden als auch des der er sie es aus bei über nach diesem
    diese dieser diesem diese dieseiner einer einem eines um zur zum oder
    wenn dann zwischen aber weil noch schon kann kein keine keinen
    """.split()
)

_EN_STOPWORDS = frozenset(
    """
    the and is are was were not with for on of a an to in it he she they
    this that these those from at by over after between but when then or
    because still can cannot no not be been being have has had its as
    """.split()
)


def detect_language(text: str) -> str:
    """Return "de" or "en": the language whose stopwords dominate the text.

    Counts occurrences of German and English function words in the lowercased
    text and returns the higher count, with English as the tie-break and the
    fallback for empty input. The two stopword sets are disjoint enough that
    short passages classify stably; this is a gate, not a linguist.
    """
    words = text.lower().split()
    if not words:
        return "en"
    german = sum(1 for w in words if w in _DE_STOPWORDS)
    english = sum(1 for w in words if w in _EN_STOPWORDS)
    return "de" if german > english else "en"


def normalize_timestamp(raw: str | datetime, source_format: str | None = None) -> datetime:
    """Normalize a timestamp to a timezone-aware `datetime`.

    A `datetime` input is returned with UTC attached when naive. A string is
    parsed with `source_format` (strptime) when given, else by dateutil with
    day-first order — the right default for European sources — and any naive
    result is assumed UTC, because the graph stores instants, not local times
    (Doc 2 §5.6). Raises `ValueError` with the raw value when parsing fails;
    the adapter converts that to a counted record-level skip.
    """
    if isinstance(raw, datetime):
        return raw if raw.tzinfo is not None else raw.replace(tzinfo=UTC)
    try:
        if source_format is not None:
            parsed = datetime.strptime(raw, source_format)
        else:
            parsed = dateutil_parser.parse(raw, dayfirst=True)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError(f"cannot parse timestamp {raw!r}") from exc
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def extract_text_from_html(html_text: str) -> str:
    """Visible text of an HTML document: markup stripped, script/style/head
    dropped, whitespace collapsed.

    Text nodes are joined with a space so adjacent block elements do not fuse
    words ("Title" + "Visible" stays two words). Plain text without markup
    passes through leniently — feed bodies are often not HTML at all. Returns
    an empty string only when the input carries no text at all.
    """
    try:
        document = html.fromstring(html_text)
    except (etree.ParserError, ValueError):
        return ""
    for element in document.xpath("//script | //style | //head"):
        element.getparent().remove(element)
    text = " ".join(document.itertext())
    return " ".join(text.split())


def extract_text_from_xml(xml_text: str, xpath: str) -> str:
    """Text of the nodes an XPath selects in an XML document, joined with
    spaces and whitespace-collapsed. Raises `ValueError` on malformed XML
    (etree) or an invalid XPath — both are record-level parse failures the
    adapter counts, never silent empties."""
    try:
        document = etree.fromstring(xml_text.encode("utf-8"))
        nodes = document.xpath(xpath)
    except (etree.XMLSyntaxError, etree.XPathError) as exc:
        raise ValueError(f"cannot extract text: {exc}") from exc
    return " ".join(" ".join((node.text or "").split()) for node in nodes)
