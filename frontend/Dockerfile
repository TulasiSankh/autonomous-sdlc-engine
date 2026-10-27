# Multi-stage Dockerfile for React Frontend with Nginx

# Stage 1: Build the static bundle
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package descriptors first to take advantage of Docker layer caching
COPY package.json package-lock.json ./
RUN npm ci

# Accept build-time API base URL argument
ARG VITE_API_BASE_URL=http://localhost:8000
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

# Copy source code and build
COPY . .
RUN npm run build

# Stage 2: Serve with ultra-lightweight Nginx alpine image (~20MB)
FROM nginx:alpine AS runner

# Copy custom Nginx configuration for SPA routing
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy compiled static assets from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
