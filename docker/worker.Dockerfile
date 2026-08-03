# LIMES — worker image | v1.0.0 | introduced by WP-37
# The ingestion worker: every CLI command runs in this container via
# `docker compose exec` (Doc 2 §13.1, §8.14). The `deps` stage is the shared
# dependency layer with the FULL dependency set — including the locked
# spaCy model wheels, the only image that installs them (D-59). It also
# carries the docker CLI and the compose plugin: the WP-28 `backup` command
# orchestrates `docker compose stop/run/start` from inside this container
# (D-57). No virtual environment inside the image; `sleep infinity` keeps
# the container up so `exec` works.
FROM python:3.12-slim-trixie AS deps

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    PATH="/uv/bin:${PATH}"

COPY --from=ghcr.io/astral-sh/uv:0.12.1 /uv /uv/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv export --frozen --no-dev --no-emit-project \
        > /tmp/limes-deps.txt \
    && uv pip install --system -r /tmp/limes-deps.txt

FROM deps AS worker

# The docker CLI and the compose v2 plugin: `limes backup` drives the host
# daemon through the socket the compose file mounts (D-57). Debian ships
# the CLI as `docker-cli`; the compose plugin is not packaged on trixie,
# so it is pinned from the upstream release as a static binary, verified
# against the release checksums (hash pinned 2026-08-03).
RUN apt-get update \
    && apt-get install -y --no-install-recommends docker-cli curl ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /usr/local/lib/docker/cli-plugins \
    && curl -fsSL -o /usr/local/lib/docker/cli-plugins/docker-compose \
        https://github.com/docker/compose/releases/download/v2.40.3/docker-compose-linux-x86_64 \
    && echo "dba9d98e1ba5bfe11d88c99b9bd32fc4a0624a30fafe68eea34d61a3e42fd372  /usr/local/lib/docker/cli-plugins/docker-compose" | sha256sum -c - \
    && chmod +x /usr/local/lib/docker/cli-plugins/docker-compose \
    && docker compose version

COPY src ./src
COPY ontology ./ontology
COPY reference_questions ./reference_questions
RUN uv pip install --system --no-deps .

CMD ["sleep", "infinity"]
