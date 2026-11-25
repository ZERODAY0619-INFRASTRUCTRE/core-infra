FROM ghcr.io/element-hq/synapse:v1.166.0

USER root
RUN sed -i "s|http://deb.debian.org|https://deb.debian.org|g" /etc/apt/sources.list.d/debian.sources && apt-get -o APT::Update::Error-Mode=any update \
    && DEBIAN_FRONTEND=noninteractive apt-get upgrade -y --no-install-recommends \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends libbrotli1 \
    && rm -rf /var/lib/apt/lists/* \
    && rm -f /usr/sbin/gosu

RUN python -m pip install --no-cache-dir "Authlib==1.9.0" "joserfc==1.8.0" \
    && python -m pip check

USER 1000:1000
