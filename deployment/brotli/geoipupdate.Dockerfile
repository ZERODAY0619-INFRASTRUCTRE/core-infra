FROM ghcr.io/maxmind/geoipupdate@sha256:51e70dd6f16cd3e4d845ac02d09940b10772a75b9d741427d235a78570923c1d
COPY brotli-libs-1.2.1-r0.apk brotli-1.2.1-r0.apk /tmp/
RUN apk add --no-network /tmp/brotli-libs-1.2.1-r0.apk /tmp/brotli-1.2.1-r0.apk \
    && rm /tmp/brotli-libs-1.2.1-r0.apk /tmp/brotli-1.2.1-r0.apk
