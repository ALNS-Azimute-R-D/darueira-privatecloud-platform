# ==============================================================================
# Build Stage
# ==============================================================================
FROM node:20-alpine AS builder

WORKDIR /app
COPY package.json ./
RUN npm install

COPY index.html ./
COPY src/ ./src/

RUN npm run build

# ==============================================================================
# Runtime Stage (Nginx unprivileged, PSS Restricted Non-root)
# ==============================================================================
FROM nginxinc/nginx-unprivileged:alpine-slim

WORKDIR /usr/share/nginx/html

COPY --from=builder --chown=101:101 /app/dist ./

EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]
