# ==============================================================================
# Runtime Stage (Non-root, PSS Restricted Compliance)
# ==============================================================================
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates && \
    rm -rf /var/lib/apt/lists/*

RUN addgroup --gid 10001 darueira && \
    adduser --uid 10001 --gid 10001 --disabled-password --gecos "" darueira && \
    chown -R darueira:darueira /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=darueira:darueira app ./app

USER 10001:10001

EXPOSE 8084

ENTRYPOINT ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8084"]
