FROM postgres:17.12-alpine3.24

USER root
RUN apk upgrade --no-cache
RUN rm /usr/local/bin/gosu \
    && adduser -D -u 999 -G postgres -h /var/lib/postgresql/data pgdata

ENV HOME=/var/lib/postgresql/data
USER pgdata
