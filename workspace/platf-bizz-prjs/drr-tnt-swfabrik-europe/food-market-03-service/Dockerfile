# ==============================================================================
# Build Stage
# ==============================================================================
FROM golang:1.24-alpine AS builder

WORKDIR /app
RUN apk add --no-cache git ca-certificates

COPY go.mod go.sum* ./
RUN go mod download

COPY . .
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -ldflags="-w -s" -o food-market-03-service ./cmd/server

# ==============================================================================
# Runtime Stage (Non-root, PSS Restricted Compliance)
# ==============================================================================
FROM alpine:3.21

WORKDIR /app
RUN apk add --no-cache ca-certificates tzdata

RUN addgroup -g 10001 darueira && \
    adduser -u 10001 -G darueira -s /bin/sh -D darueira && \
    chown -R darueira:darueira /app

USER 10001:10001

COPY --from=builder --chown=10001:10001 /app/food-market-03-service /app/food-market-03-service

EXPOSE 8083

ENTRYPOINT ["/app/food-market-03-service"]
