# Multi-stage non-root build for drr-iam-authz-svc
FROM golang:1.24-alpine AS builder

WORKDIR /workspace

# Install ca-certificates and git
RUN apk add --no-cache ca-certificates git

# Cache dependencies
COPY go.mod go.sum* ./
RUN go mod download || true

# Copy source code
COPY . .

# Build statically linked binary
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build \
    -ldflags="-w -s" \
    -o /bin/drr-iam-authz-svc \
    ./cmd/server/main.go

# Production non-root runtime image
FROM gcr.io/distroless/static-debian12:nonroot

WORKDIR /app
COPY --from=builder /bin/drr-iam-authz-svc /app/drr-iam-authz-svc

USER 10001:10001

EXPOSE 8080

ENTRYPOINT ["/app/drr-iam-authz-svc"]
