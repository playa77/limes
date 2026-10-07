FROM neo4j:2026.06-community
USER root
RUN apt-get update && apt-get install -y --no-install-recommends python3 \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /data/archive/dumps /logs \
    && chown -R 7474:7474 /data /logs
COPY --chown=7474:7474 docker/neo4j_control.py /opt/limes/neo4j_control.py
ARG LIMES_REVISION=dev
LABEL org.opencontainers.image.revision=$LIMES_REVISION
ENV LIMES_REVISION=$LIMES_REVISION
USER 7474:7474
ENTRYPOINT ["python3", "/opt/limes/neo4j_control.py"]
CMD []
