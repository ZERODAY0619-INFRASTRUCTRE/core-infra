ARG BASE_IMAGE
FROM ${BASE_IMAGE}
USER root
# Keep the existing runtime security updates when rebasing the Caddy source.
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/* \
    && rm -f /usr/bin/pebble
USER caddy
