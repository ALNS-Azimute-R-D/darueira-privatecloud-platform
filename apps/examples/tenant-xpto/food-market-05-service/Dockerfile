# ==============================================================================
# Build Stage
# ==============================================================================
FROM node:20-alpine AS builder

WORKDIR /app
COPY package.json ./
RUN npm install

COPY tsconfig*.json nest-cli.json ./
COPY src/ ./src/
RUN npm run build

# ==============================================================================
# Runtime Stage (Non-root, PSS Restricted Compliance)
# ==============================================================================
FROM node:20-alpine

WORKDIR /app

RUN addgroup -g 10001 darueira && \
    adduser -u 10001 -G darueira -s /bin/sh -D darueira && \
    chown -R darueira:darueira /app

COPY package.json ./
RUN npm install --omit=dev

COPY --from=builder --chown=10001:10001 /app/dist ./dist

USER 10001:10001

EXPOSE 8085

ENTRYPOINT ["node", "dist/main.js"]
