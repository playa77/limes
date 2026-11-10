FROM neo4j:2026.06-community AS build
USER root
RUN --mount=type=bind,source=docker/neo4j_control.py,target=/run/neo4j_control.py,readonly \
    apt-get update && apt-get install -y --no-install-recommends python3 \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /data/archive/dumps /logs \
    && chown -R 7474:7474 /data /logs \
    && mkdir -p /opt/limes \
    && cp /run/neo4j_control.py /opt/limes/neo4j_control.py \
    && chown 7474:7474 /opt/limes/neo4j_control.py
# Keep one final filesystem layer rather than a full VFS copy for every base
# layer. Preserve the vendor runtime paths, Java, volumes and service ports.
FROM scratch AS neo4j
VOLUME ["/data", "/logs"]
WORKDIR /var/lib/neo4j
COPY --from=build / /
ENV PATH="/var/lib/neo4j/bin:/opt/java/openjdk/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" \
    JAVA_HOME=/opt/java/openjdk \
    NEO4J_EDITION=community \
    NEO4J_HOME=/var/lib/neo4j \
    LANG=C.UTF-8
EXPOSE 7473 7474 7687
ARG LIMES_REVISION=dev
LABEL org.opencontainers.image.revision=$LIMES_REVISION
ENV LIMES_REVISION=$LIMES_REVISION
USER 7474:7474
ENTRYPOINT ["python3", "/opt/limes/neo4j_control.py"]
CMD []
