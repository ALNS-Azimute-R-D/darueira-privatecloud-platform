FROM golang:1.24-alpine AS builder

WORKDIR /app
COPY go.mod ./
RUN go mod download

COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o drr-tenant-svc cmd/main.go

FROM gcr.io/distroless/static-debian12:nonroot

WORKDIR /
COPY --from=builder /app/drr-tenant-svc /drr-tenant-svc

USER 10001:10001
EXPOSE 8081

ENTRYPOINT ["/drr-tenant-svc"]
