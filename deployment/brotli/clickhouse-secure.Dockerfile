FROM clickhouse/clickhouse-server:26.9.39.7-alpine

USER root
RUN apk update \
    && apk upgrade --no-cache \
    && rm -rf /var/cache/apk/*
