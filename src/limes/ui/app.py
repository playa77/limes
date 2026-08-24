# src/limes/ui/app.py | v1.0.0 | introduced by WP-36
"""The Dash application (Doc 1 §4.13, Doc 2 §8.13): layout plus callback
registration, runnable as `python -m limes.ui.app` (the WP-37 `ui` service
entry point).

The app holds no credentials and performs no database access (Doc 1 §7.4):
every read goes through `api_client` to the API. Constructing the app
performs no HTTP either — the boot callback loads the schema and status
after the page renders, so a temporarily unreachable API degrades the UI
instead of killing its startup.
"""

from __future__ import annotations

from dash import Dash

from limes.ui.callbacks import builder as builder_callbacks
from limes.ui.callbacks import query as query_callbacks
from limes.ui.callbacks import selection as selection_callbacks
from limes.ui.callbacks import temporal as temporal_callbacks
from limes.ui.layout import layout


def create_app() -> Dash:
    """Build the Dash application with all callbacks registered."""
    app = Dash(
        __name__,
        title="LIMES",
        update_title="LIMES",  # the page title stays put while callbacks run
        suppress_callback_exceptions=True,
    )
    app.layout = layout()
    selection_callbacks.register(app)
    query_callbacks.register(app)
    builder_callbacks.register(app)
    temporal_callbacks.register(app)
    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=False)
