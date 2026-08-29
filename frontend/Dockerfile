# syntax=docker/dockerfile:1

FROM node:26-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# --- Développement : Vite avec hot-reload ---
FROM deps AS dev
WORKDIR /app
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]

# --- Build des assets statiques ---
FROM deps AS build
WORKDIR /app
COPY . .
ARG VITE_API_BASE_URL=
ARG VITE_MAIL_UI_URL=http://localhost:8025
ARG VITE_REDIS_INSIGHT_URL=http://localhost:5540
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL \
    VITE_MAIL_UI_URL=$VITE_MAIL_UI_URL \
    VITE_REDIS_INSIGHT_URL=$VITE_REDIS_INSIGHT_URL
RUN npm run build

# --- Production : Nginx (variante unprivileged) sert le build Vite ---
# nginx-unprivileged tourne en non-root (uid 101), écoute sur 8080 et met pid +
# fichiers temporaires sous /tmp → compatible runAsNonRoot + readOnlyRootFilesystem.
FROM nginxinc/nginx-unprivileged:1.27-alpine AS production
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]
