# src/limes/ui/components/console.py | v1.0.0 | introduced by WP-36
"""The NL input and editable Cypher console (Doc 1 §6.5, AC-26).

The textarea is an output of every query callback: the NL path writes the
generated Cypher into it, the Cypher path writes the executed (validated)
Cypher, so whatever ran is displayed, editable, and re-runnable. Errors
from the API land in the shared error display with the §6 envelope's code.
The console itself is static — the dynamic parts are callback outputs.
"""

from __future__ import annotations

from dash import dcc, html


def render() -> html.Div:
    """The console block: question input, generated-Cypher textarea, the two
    run buttons, and the error display."""
    return html.Div(
        [
            html.H4("Ask / query", style={"margin": "0 0 8px 0", "font-size": "14px"}),
            html.Label("Natural-language question", style={"font-size": "12px"}),
            dcc.Input(
                id="nl-input",
                type="text",
                placeholder="e.g. Which corporations are headquartered in Berlin?",
                n_submit=0,
                style={"width": "100%", "box-sizing": "border-box"},
            ),
            html.Button(
                "Run question",
                id="nl-run",
                n_clicks=0,
                style={"margin": "4px 0", "font-size": "12px"},
            ),
            html.Label("Cypher (generated or hand-written)", style={"font-size": "12px"}),
            dcc.Textarea(
                id="cypher-textarea",
                value="",
                placeholder="Cypher query (generated or hand-written)",
                style={
                    "width": "100%",
                    "height": "90px",
                    "font-family": "monospace",
                    "box-sizing": "border-box",
                },
            ),
            html.Button(
                "Run Cypher",
                id="cypher-run",
                n_clicks=0,
                style={"margin": "4px 0", "font-size": "12px"},
            ),
            html.Div(
                id="error-display",
                style={"color": "#8b1a10", "font-size": "12px", "min-height": "18px"},
            ),
        ]
    )
