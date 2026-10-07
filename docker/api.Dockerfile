# LIMES — api image | v1.0.0 | introduced by WP-37
# The FastAPI service (Doc 2 §13.1). The `deps` stage is the shared
# dependency layer: Python 3.12, all project dependencies from the committed
# lockfile, installed directly into the system prefix — no virtual
# environment inside the image (Doc 2 §13.1). The two spaCy model wheels are
# pruned from the export: only the worker image installs them (AC-34
# sibling rule). The CMD uses the factory form because `limes.api.main`
# exposes `create_app`, not a module-level `app` (ledger D-58).
FROM python:3.12-slim-trixie AS deps

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_NO_CACHE=1 \
    PATH="/uv/bin:${PATH}"

COPY --from=ghcr.io/astral-sh/uv:0.12.1 /uv /uv/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY desktop/pyproject.toml ./desktop/pyproject.toml
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export SSL_CERT_FILE=/run/secrets/proxy_ca; fi; \
    uv export --frozen --no-dev --no-emit-project \
        --prune de-core-news-md --prune en-core-web-md \
        > /tmp/limes-deps.txt \
    && uv pip install --system -r /tmp/limes-deps.txt

FROM deps AS api

# The ontology artifact at its configured container path: the startup
# handler loads `/app/ontology/ontology.yaml` (Doc 2 §4.2) and the
# downgrade guard compares against the version stamped in the graph.
COPY --chown=0:0 . .
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export SSL_CERT_FILE=/run/secrets/proxy_ca; fi; \
    uv pip install --system --no-deps . \
    && chmod -R a+rX /app \
    && groupadd --gid 7474 limes && useradd --uid 7474 --gid 7474 --no-create-home limes \
    && mkdir -p /data/jobs /data/models && chown -R 7474:7474 /data
ARG LIMES_REVISION=dev
LABEL org.opencontainers.image.revision=$LIMES_REVISION
ENV LIMES_REVISION=$LIMES_REVISION
USER 7474:7474
EXPOSE 8000
CMD ["uvicorn", "limes.api.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
