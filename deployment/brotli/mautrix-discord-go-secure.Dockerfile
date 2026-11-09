FROM golang:1.27.3-alpine3.24@sha256:b8c9b82affbbb82a020bbcf998dad2ba9516944ac7e883524642a481a9505e9c AS builder

RUN apk add --no-cache git build-base olm-dev cmake
RUN git clone --depth 1 --branch 3.2.16 https://gitlab.matrix.org/matrix-org/olm.git /olm \
    && test "$(git -C /olm rev-parse HEAD)" = 7e0c8277032e40308987257b711b38af8d77cc69 \
    && cmake -S /olm -B /olm/build -DBUILD_SHARED_LIBS=OFF -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
    && cmake --build /olm/build --parallel 4 \
    && cp /olm/build/libolm.a /usr/local/lib/libolm.a
RUN git clone --depth 1 --branch v0.7.7 https://github.com/mautrix/discord.git /src \
    && test "$(git -C /src rev-parse HEAD)" = c62165a46109d7c824bc0b4bb067ba02ea6528f1
WORKDIR /src
RUN go get golang.org/x/net@v0.60.0 \
    && CGO_LDFLAGS=-L/usr/local/lib go build -trimpath \
        -ldflags '-s -w -linkmode external -extldflags "-static" -X main.Tag=v0.7.7 -X main.Commit=c62165a46109d7c824bc0b4bb067ba02ea6528f1 -X main.BuildTime=2026-10-24' \
        -o /mautrix-discord .

FROM mautrix-discord:security-20261024
COPY --from=builder /mautrix-discord /usr/bin/mautrix-discord
