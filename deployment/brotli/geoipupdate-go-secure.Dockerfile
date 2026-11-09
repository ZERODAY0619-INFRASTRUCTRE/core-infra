FROM golang:1.27.3@sha256:f20d83a83e18dbd2a4714b8ffd4b30b287b6243962dd75608e86abcc63ba4efc AS builder

RUN git clone --depth 1 --branch v8.0.0 https://github.com/maxmind/geoipupdate.git /src \
    && test "$(git -C /src rev-parse HEAD)" = 07618e0e7cacbe7aaebbc26cafb54c2a9f2f3bc3
WORKDIR /src
RUN go get golang.org/x/net@v0.60.0 \
    && CGO_ENABLED=0 go build -trimpath \
        -ldflags '-s -w -X main.version=8.0.0-security-20261024' \
        -o /geoipupdate ./cmd/geoipupdate

FROM cpm-geoipupdate:8.0.0-security-20261024
COPY --from=builder /geoipupdate /usr/bin/geoipupdate
