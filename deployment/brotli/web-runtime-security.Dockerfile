ARG BASE_IMAGE
FROM ${BASE_IMAGE}
USER root
RUN apt-get -o APT::Update::Error-Mode=any update \
    && DEBIAN_FRONTEND=noninteractive apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*
USER nextjs
