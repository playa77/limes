# LIMES — ui image | v1.0.0 | introduced by WP-37
# The Dash application (Doc 2 §13.1), runnable as `python -m limes.ui.app`
# (the phase-8 ledger verified this entry point works). Same shared
# dependency layer as the api image — including the spaCy model prune: only
# the worker installs the models. The UI holds no credentials (Doc 1 §7.4);
# it reads only `LIMES_API_BASE_URL` from the environment (D-09), which the
# compose `ui` service supplies.
FROM python:3.12-slim-trixie AS deps

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    PATH="/uv/bin:${PATH}"

COPY --from=ghcr.io/astral-sh/uv:0.12.1 /uv /uv/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv export --frozen --no-dev --no-emit-project \
        --prune de-core-news-md --prune en-core-web-md \
        > /tmp/limes-deps.txt \
    && uv pip install --system -r /tmp/limes-deps.txt

FROM deps AS ui

COPY README.md ./README.md
COPY src ./src
RUN uv pip install --system --no-deps .

EXPOSE 8050
CMD ["python", "-m", "limes.ui.app"]
