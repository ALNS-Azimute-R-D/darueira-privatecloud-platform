FROM golang:1.24-alpine AS builder

WORKDIR /app
COPY go.mod ./
RUN go mod download

COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o drr-env-orchestrator-svc cmd/main.go

FROM gcr.io/distroless/static-debian12:nonroot

WORKDIR /
COPY --from=builder /app/drr-env-orchestrator-svc /drr-env-orchestrator-svc

USER 10001:10001
EXPOSE 8082

ENTRYPOINT ["/drr-env-orchestrator-svc"]
