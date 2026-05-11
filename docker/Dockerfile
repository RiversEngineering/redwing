# ---- Stage 1: Build Svelte dashboard ----
FROM node:20-slim AS dashboard-builder

WORKDIR /build/dashboard
COPY dashboard/package.json dashboard/package-lock.json* ./
RUN npm ci

COPY dashboard/ ./
RUN npm run build


# ---- Stage 2: Runtime image ----
FROM python:3.11-slim

# System deps for OpenCV + serial
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    udev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir \
    "fastapi>=0.111" \
    "uvicorn[standard]>=0.30" \
    "pyzmq>=26.0" \
    "pyserial>=3.5" \
    "pyserial-asyncio>=0.6" \
    "numpy>=1.24" \
    "opencv-python-headless>=4.8" \
    "websockets>=12.0"

# Install the redwing library itself
COPY redwing/ ./redwing/
RUN pip install --no-cache-dir -e .

# Copy daemon
COPY daemon/ ./daemon/

# Copy built dashboard static files from stage 1
COPY --from=dashboard-builder /build/dashboard/dist ./dashboard/dist

# Persistent student workspace is bind-mounted at runtime (see docker-compose.yml)
RUN mkdir -p /workspace

EXPOSE 8080

CMD ["python", "-m", "daemon.main"]
