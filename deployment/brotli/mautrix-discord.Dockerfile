FROM dock.mau.dev/mautrix/discord@sha256:065405ca2f961b2687ca577c4eb65592c139d641342a9611d98b5394f30cf84a
COPY brotli-libs-1.2.1-r0.apk /tmp/
RUN apk add --no-network /tmp/brotli-libs-1.2.1-r0.apk \
    && rm /tmp/brotli-libs-1.2.1-r0.apk
