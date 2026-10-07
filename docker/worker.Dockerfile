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
        > /tmp/limes-deps.txt \
    && uv pip install --system -r /tmp/limes-deps.txt

FROM deps AS worker

COPY --chown=0:0 . .
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export SSL_CERT_FILE=/run/secrets/proxy_ca; fi; \
    uv pip install --system --no-deps . \
    && chmod -R a+rX /app \
    && groupadd --gid 7474 limes && useradd --uid 7474 --gid 7474 --no-create-home limes \
    && mkdir -p /data/archive /data/jobs /data/models /app/config /app/gold_set \
    && chown -R 7474:7474 /data /app/config /app/gold_set
ARG LIMES_REVISION=dev
LABEL org.opencontainers.image.revision=$LIMES_REVISION
ENV LIMES_REVISION=$LIMES_REVISION
USER 7474:7474
CMD ["python", "-m", "limes.operations.worker"]
