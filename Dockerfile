# ── Stage 0: Frontend Builder ─────────────────────────────────────────────────
FROM node:20-alpine AS frontend-builder
WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ── Stage 1: Builder ──────────────────────────────────────────────────────────
FROM python:3.11-slim-bookworm AS builder

# System deps for OpenCV, psycopg2, cryptography
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        libgl1 \
        libglib2.0-0 \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Install Python deps into /install prefix (copied to runtime stage)
COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install --prefix=/install --no-cache-dir -r requirements.txt


# ── Stage 2: Runtime ──────────────────────────────────────────────────────────
FROM python:3.11-slim-bookworm AS runtime

LABEL org.opencontainers.image.title="Cortex API"
LABEL org.opencontainers.image.version="1.4.0"
LABEL org.opencontainers.image.description="Structural intelligence defect detection platform"

# Runtime system deps only
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        libgl1 \
        libglib2.0-0 \
        libgomp1 \
        curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 1000 -s /bin/bash cortex

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# App code
WORKDIR /app
COPY --chown=cortex:cortex . .

# Copy compiled frontend from frontend-builder
COPY --from=frontend-builder --chown=cortex:cortex /app/out /app/frontend/out

# Make entrypoint script executable and create backup of initial mock data
RUN chmod +x /app/scripts/entrypoint.sh \
    && cp -r /app/data /app/data_backup \
    && mkdir -p /tmp/cortex_uploads \
    && chown -R cortex:cortex /app /tmp/cortex_uploads

ENTRYPOINT ["/app/scripts/entrypoint.sh"]

USER cortex

# Expose port
EXPOSE 8000

# Default command to launch the unified FastAPI + static Next.js frontend server
CMD ["python", "run_frontend.py", "--no-browser", "--port", "8000"]


