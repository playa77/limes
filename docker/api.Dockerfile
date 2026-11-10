# Install the frozen runtime and allowlisted source in one filesystem layer.
# Mount the installer only for the build; rootless VFS need not copy it or a
# complete dependency tree into additional source/install layers.
FROM python:3.12-slim-trixie AS build
ENV UV_LINK_MODE=copy \
    UV_NO_CACHE=1
WORKDIR /app
RUN --mount=type=bind,source=.,target=/run/limes-source,readonly \
    --mount=from=ghcr.io/astral-sh/uv:0.12.1,source=/uv,target=/run/uv,readonly \
    --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export SSL_CERT_FILE=/run/secrets/proxy_ca; fi; \
    cp -R /run/limes-source/. /app/ \
    && /run/uv export --frozen --no-dev --no-emit-project \
        --prune de-core-news-md --prune en-core-web-md \
        > /tmp/limes-deps.txt \
    && /run/uv pip install --system -r /tmp/limes-deps.txt \
    && /run/uv pip install --system --no-deps . \
    && chmod -R a+rX /app \
    && groupadd --gid 7474 limes && useradd --uid 7474 --gid 7474 --no-create-home limes \
    && mkdir -p /data/jobs /data/models && chown -R 7474:7474 /data
# Flatten the installed filesystem: VFS builders otherwise retain a complete
# root copy for every inherited layer. The installer stays outside the runtime.
FROM scratch AS api
WORKDIR /app
COPY --from=build / /
ENV PATH="/usr/local/bin:/usr/local/sbin:/usr/sbin:/usr/bin:/sbin:/bin" \
    LANG=C.UTF-8
ARG LIMES_REVISION=dev
LABEL org.opencontainers.image.revision=$LIMES_REVISION
ENV LIMES_REVISION=$LIMES_REVISION
USER 7474:7474
EXPOSE 8000
CMD ["uvicorn", "limes.api.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
