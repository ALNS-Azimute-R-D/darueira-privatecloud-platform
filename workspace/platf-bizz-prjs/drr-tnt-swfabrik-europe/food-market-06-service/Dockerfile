# ==============================================================================
# Build Stage
# ==============================================================================
FROM mcr.microsoft.com/dotnet/sdk:8.0-alpine AS builder

WORKDIR /app
COPY food-market-06-service.csproj ./
RUN dotnet restore

COPY src/ ./src/
RUN dotnet publish -c Release -o /app/out

# ==============================================================================
# Runtime Stage (Non-root, PSS Restricted Compliance)
# ==============================================================================
FROM mcr.microsoft.com/dotnet/aspnet:8.0-alpine

WORKDIR /app

RUN addgroup -g 10001 darueira && \
    adduser -u 10001 -G darueira -s /bin/sh -D darueira && \
    chown -R darueira:darueira /app

COPY --from=builder --chown=10001:10001 /app/out ./

USER 10001:10001

ENV ASPNETCORE_URLS=http://0.0.0.0:8086

EXPOSE 8086

ENTRYPOINT ["dotnet", "food-market-06-service.dll"]
