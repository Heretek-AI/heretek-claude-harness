# Heretek Swarm Frontend
# Multi-stage build: compile TypeScript + Vite inside Docker, serve with nginx

# =============================================================================
# Stage 1: Builder — compile TypeScript and Vite assets inside Docker
# =============================================================================
FROM node:26.2.0-alpine AS builder

# Accept build-time env vars for Vite
ARG VITE_API_URL
ARG VITE_API_HOST
ENV VITE_API_URL=${VITE_API_URL}
ENV VITE_API_HOST=${VITE_API_HOST}

WORKDIR /app

# Copy package files and local tarballs first for layer caching
COPY package*.json vite-*.tgz ./

# Deterministic install using package-lock.json
RUN npm ci

# Copy all source
COPY . .

# Compile TypeScript and build Vite assets
RUN npm run build

# =============================================================================
# Stage 2: Production — serve built assets with nginx
# =============================================================================
FROM nginx:alpine AS production

# Create non-root user for security (S6471 fix)
RUN addgroup -g 1001 -S appgroup && adduser -u 1001 -S appuser -G appgroup

# Copy custom nginx config (remove user directive)
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Create nginx directories for non-root user
RUN mkdir -p /var/cache/nginx/client_temp /run && \
    chown -R appuser:appgroup /var/cache/nginx /run

# Copy built assets from builder stage, not local filesystem
COPY --from=builder --chown=appuser:appgroup /app/dist/ /usr/share/nginx/html/

# Expose port
EXPOSE 80

# Health check - use 127.0.0.1 instead of localhost (IPv6 vs IPv4 issue)
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget --spider http://127.0.0.1/ || exit 1

# Start nginx as non-root user
USER appuser

# Start nginx in foreground
CMD ["nginx", "-g", "daemon off;"]
