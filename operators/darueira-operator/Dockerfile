# Multi-stage non-root build for darueira-operator
FROM golang:1.24-alpine AS builder

WORKDIR /workspace

RUN apk add --no-cache ca-certificates git

COPY go.mod go.sum* ./
RUN go mod download || true

COPY . .

RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build \
    -ldflags="-w -s" \
    -o /bin/darueira-operator \
    ./main.go

# Production distroless non-root image
FROM gcr.io/distroless/static-debian12:nonroot

WORKDIR /app
COPY --from=builder /bin/darueira-operator /app/darueira-operator

USER 10001:10001

ENTRYPOINT ["/app/darueira-operator"]
