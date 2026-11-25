FROM golang:1.27.4@sha256:205c7636d74e0ffbe3d007162df7d74f859f5a8c8322dfb9f907977686c126cf AS builder

RUN git clone --depth 1 --branch v8.0.0 https://github.com/maxmind/geoipupdate.git /src \
    && test "$(git -C /src rev-parse HEAD)" = 07618e0e7cacbe7aaebbc26cafb54c2a9f2f3bc3
WORKDIR /src
RUN go get golang.org/x/net@v0.62.0 \
    && CGO_ENABLED=0 go build -trimpath \
        -ldflags '-s -w -X main.version=8.0.0-security-20261119' \
        -o /geoipupdate ./cmd/geoipupdate

FROM cpm-geoipupdate:8.0.0-security-20261024
RUN apk upgrade --no-cache
COPY --from=builder /geoipupdate /usr/bin/geoipupdate
