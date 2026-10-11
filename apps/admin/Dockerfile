# syntax=docker/dockerfile:1

# ---- build -----------------------------------------------------------------
FROM node:25-alpine AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
# Empty base URL: the browser calls the same origin and nginx proxies to the API.
ARG VITE_API_BASE_URL=
ARG VITE_API_TOKEN=
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL \
    VITE_API_TOKEN=$VITE_API_TOKEN
RUN npm run build

# ---- serve -----------------------------------------------------------------
FROM nginx:1.29-alpine AS serve

# The official nginx image runs envsubst over /etc/nginx/templates/*.template at
# start-up, so API_UPSTREAM can be changed per deployment without a rebuild.
ENV API_UPSTREAM=http://api:8000
ENV NGINX_ENVSUBST_FILTER=^API_UPSTREAM$

COPY nginx.conf /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s CMD wget -qO- http://127.0.0.1/ >/dev/null || exit 1
