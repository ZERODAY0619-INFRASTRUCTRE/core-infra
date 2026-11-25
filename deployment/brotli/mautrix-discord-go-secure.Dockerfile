FROM golang:1.27.4-alpine3.24@sha256:70bd7ddea8b6cbe5d6943cde279d6b67feb10cc924fb9100d1d8757c1575b280 AS builder

RUN apk add --no-cache git build-base olm-dev cmake
RUN git clone --depth 1 --branch 3.2.16 https://gitlab.matrix.org/matrix-org/olm.git /olm \
    && test "$(git -C /olm rev-parse HEAD)" = 7e0c8277032e40308987257b711b38af8d77cc69 \
    && cmake -S /olm -B /olm/build -DBUILD_SHARED_LIBS=OFF -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
    && cmake --build /olm/build --parallel 4 \
    && cp /olm/build/libolm.a /usr/local/lib/libolm.a
RUN git clone --depth 1 --branch v0.7.7 https://github.com/mautrix/discord.git /src \
    && test "$(git -C /src rev-parse HEAD)" = c62165a46109d7c824bc0b4bb067ba02ea6528f1
WORKDIR /src
RUN go get golang.org/x/net@v0.62.0 \
    && CGO_LDFLAGS=-L/usr/local/lib go build -trimpath \
        -ldflags '-s -w -linkmode external -extldflags "-static" -X main.Tag=v0.7.7 -X main.Commit=c62165a46109d7c824bc0b4bb067ba02ea6528f1 -X main.BuildTime=2026-11-19' \
        -o /mautrix-discord .

FROM mautrix-discord:security-20261024
RUN apk upgrade --no-cache
COPY --from=builder /mautrix-discord /usr/bin/mautrix-discord
