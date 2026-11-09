FROM clickhouse/clickhouse-server@sha256:8f1dd1ec7213410276c8e9aee11b25b458fe9d53eee13ad8cfdf7c79e36aad17

USER root
RUN apk update \
    && apk upgrade --no-cache \
    && rm -rf /var/cache/apk/*
