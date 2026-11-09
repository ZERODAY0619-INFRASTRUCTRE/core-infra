ARG BASE_IMAGE=alpine:3.24
FROM ${BASE_IMAGE}

USER root
RUN apk update \
    && apk upgrade --no-cache \
    && rm -rf /var/cache/apk/*
