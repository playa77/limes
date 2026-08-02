# src/limes/ui/components/provenance.py | v1.0.0 | introduced by WP-36
"""The provenance panel (Doc 1 §6.5, AC-28): the full §5.6 assertion
metadata of the selected edge — source, trust, confidence, validity and
belief intervals, model and prompt versions, assertion id — plus the
originating sentence for news-extracted assertions.

The sentence is fetched through the API (`get_entity` on the evidence
document, the sanctioned read path); when the graph holds no document
entity the panel states so explicitly and shows the evidence coordinates
instead — nothing is fabricated (D-10). The panel is the only consumer of
`selection` beyond the panes.
"""

from __future__ import annotations

from typing import Any, Protocol

from dash import html


class ApiClient(Protocol):
    """The API surface the provenance panel needs: the evidence-document
    read. Structural — the `api_client` module satisfies it at runtime."""

    def get_entity(self, entity_id: str) -> dict[str, Any]: ...


def _row(label: str, value: Any) -> html.Div:
    text = "—" if value is None or value == "" else str(value)
    return html.Div(
        [
            html.Span(f"{label}: ", style={"font-weight": "600"}),
            html.Span(text, style={"word-break": "break-all"}),
        ],
        style={"font-size": "12px", "margin": "2px 0"},
    )


def _property_table(properties: dict[str, Any]) -> list[html.Div]:
    return [
        _row(str(name), value)
        for name, value in sorted(properties.items())
        if name != "label_embedding"
    ]


def _originating_sentence(edge: dict[str, Any], api: ApiClient) -> tuple[str | None, str | None]:
    """(sentence, note) for an edge's evidence: the sentence is the evidence
    span of the evidence document's body, when both exist; the note explains
    when either is missing."""
    document_id = edge.get("evidence_document_id")
    if not document_id:
        return None, None
    start, end = edge.get("evidence_start"), edge.get("evidence_end")
    try:
        document = api.get_entity(str(document_id))
    except Exception:
        return None, "evidence document not available through the API"
    body = (document.get("entity") or {}).get("properties", {}).get("body")
    if not body or not isinstance(start, int) or not isinstance(end, int):
        return None, "evidence document carries no extractable body"
    sentence = body[start:end]
    return sentence, None


def render(selection: dict[str, Any] | None, api: ApiClient) -> html.Div:
    """The provenance panel for the current selection."""
    if not selection:
        return html.Div(
            [
                html.H4("Provenance", style={"margin": "0 0 8px 0", "font-size": "14px"}),
                "Select an edge or node.",
            ],
            style={"font-size": "12px", "color": "#666"},
        )

    rows: list[Any] = [html.H4("Provenance", style={"margin": "0 0 8px 0", "font-size": "14px"})]
    if selection.get("kind") == "edge":
        edge = selection.get("edge") or {}
        rows.append(_row("Relation", edge.get("relation")))
        rows.append(_row("From", edge.get("subject_id")))
        rows.append(_row("To", edge.get("object_id")))
        rows.append(_row("Source", edge.get("source_id")))
        rows.append(_row("Source trust", edge.get("source_trust")))
        rows.append(_row("Confidence", edge.get("confidence")))
        rows.append(_row("Valid from", edge.get("valid_from")))
        rows.append(_row("Valid to", edge.get("valid_to")))
        rows.append(_row("Recorded at", edge.get("recorded_at")))
        rows.append(_row("Retracted at", edge.get("retracted_at")))
        rows.append(_row("Extractor model", edge.get("extractor_model")))
        rows.append(_row("Prompt version", edge.get("prompt_version")))
        rows.append(_row("Schema version", edge.get("schema_version")))
        rows.append(_row("Ontology version", edge.get("ontology_version")))
        rows.append(_row("Assertion id", edge.get("assertion_id")))
        sentence, note = _originating_sentence(edge, api)
        if sentence is not None:
            rows.append(
                html.Div("Originating sentence", style={"font-weight": "600", "margin-top": "6px"})
            )
            rows.append(
                html.Div(
                    f"“{sentence}”",
                    style={"font-style": "italic", "font-size": "12px", "margin": "2px 0"},
                )
            )
            rows.append(
                _row("Evidence span", f"{edge.get('evidence_start')}:{edge.get('evidence_end')}")
            )
        elif edge.get("evidence_document_id"):
            rows.append(_row("Evidence document", edge.get("evidence_document_id")))
            rows.append(
                _row("Evidence span", f"{edge.get('evidence_start')}:{edge.get('evidence_end')}")
            )
            if note:
                rows.append(html.Div(note, style={"font-size": "12px", "color": "#7a5b00"}))
    else:
        entity = selection.get("entity") or {}
        rows.append(_row("Type", entity.get("type")))
        rows.append(_row("Entity id", entity.get("entity_id")))
        try:
            detail = api.get_entity(str(entity.get("entity_id")))
        except Exception:
            detail = {}
        fetched = detail.get("entity") or {}
        if fetched.get("properties"):
            rows.append(html.Div("Properties", style={"font-weight": "600", "margin-top": "6px"}))
            rows.extend(_property_table(fetched.get("properties") or {}))
        summary = detail.get("edge_summary") or {}
        if summary.get("out") or summary.get("in"):
            rows.append(html.Div("Edge summary", style={"font-weight": "600", "margin-top": "6px"}))
            for direction in ("out", "in"):
                for relation, count in sorted((summary.get(direction) or {}).items()):
                    rows.append(_row(f"{direction} · {relation}", count))
    return html.Div(rows)
