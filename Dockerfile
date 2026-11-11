# syntax=docker/dockerfile:1
# ---------- Étape 1 : interface Svelte compilée ----------
FROM node:22-bookworm-slim AS interface
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN mkdir -p /app && npx vite build --outDir /app/static --emptyOutDir

# ---------- Étape 2 : dépendances Python compilées en roues ----------
FROM python:3.12-slim-bookworm AS builder
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends gcc libffi-dev \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

# pandoc récent (celui de Debian bookworm, 2.17, est trop ancien pour --split-level)
ARG PANDOC_VERSION=3.1.3
ADD https://github.com/jgm/pandoc/releases/download/${PANDOC_VERSION}/pandoc-${PANDOC_VERSION}-1-amd64.deb /build/pandoc.deb

# ---------- Étape 3 : image d'exécution ----------
FROM python:3.12-slim-bookworm
LABEL org.opencontainers.image.title="kit-urgence" \
      org.opencontainers.image.description="Kit d'urgence numérique : générateur, livraison vers la liseuse, interface" \
      org.opencontainers.image.source="https://github.com/baloodusudouest/kit-urgence"

# pandoc : EPUB ; qpdf : fusion, chiffrement AES-256 et contrôle ; pango : WeasyPrint (PDF papier)
# gosu : abandon des droits root ; tzdata : dates françaises
COPY --from=builder /build/pandoc.deb /tmp/pandoc.deb
RUN apt-get update && apt-get install -y --no-install-recommends \
        /tmp/pandoc.deb qpdf gosu tzdata \
        libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/* /tmp/pandoc.deb

COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

WORKDIR /app
COPY app ./app
COPY --from=interface /app/static ./app/static
COPY assets ./assets
COPY seed ./seed
COPY entrypoint.sh /entrypoint.sh
RUN chmod 755 /entrypoint.sh

ENV TZ=Europe/Paris \
    KIT_DATA=/data \
    KIT_STATE=/state \
    KIT_ASSETS=/app/assets \
    PYTHONUNBUFFERED=1

EXPOSE 8095
HEALTHCHECK --interval=60s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8095/health')" || exit 1
ENTRYPOINT ["/entrypoint.sh"]
