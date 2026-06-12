FROM golang:1.26.1-alpine AS builder

WORKDIR /src

ARG TARGETOS=linux
ARG TARGETARCH

COPY go.mod go.sum ./
RUN go mod download

COPY . .

RUN CGO_ENABLED=0 GOOS=${TARGETOS:-linux} GOARCH=${TARGETARCH} \
    go build -trimpath -ldflags="-s -w" -o /out/go-llm-proxy .

FROM alpine:3.21

RUN addgroup -S app && adduser -S -G app app \
    && apk add --no-cache ca-certificates \
       poppler-utils \
       python3

WORKDIR /app

COPY --from=builder /out/go-llm-proxy /usr/local/bin/go-llm-proxy
COPY scripts/generate-model-config.py /usr/local/bin/generate-model-config
COPY scripts/docker-entrypoint.sh /usr/local/bin/docker-entrypoint
COPY scripts/baked-config.yaml /usr/local/share/go-llm-proxy/config.yaml
RUN chmod +x /usr/local/bin/generate-model-config /usr/local/bin/docker-entrypoint

RUN mkdir -p /config && chown app:app /config

USER app

EXPOSE 8080

ENTRYPOINT ["/usr/local/bin/docker-entrypoint"]
CMD ["-config", "/config/config.yaml"]
