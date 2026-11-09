ARG BASE_IMAGE
FROM ghcr.io/techarohq/anubis@sha256:5fcbce70ee6168be5b226d19bec90111d0acd0daf13028fa06b044cf3ebbbd5f AS updated_anubis
FROM oven/bun:1.4.4-slim@sha256:1846adf22496bd711036aae8be147e57bdebbaea2e5264e3e0b5af1db187d9a4 AS patched_bun
FROM ${BASE_IMAGE}

USER root
COPY --from=patched_bun /usr/local/bin/bun /usr/local/bin/bun
COPY --from=updated_anubis /ko-app/anubis /ko-app/anubis
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*
