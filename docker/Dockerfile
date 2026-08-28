# ---- Stage 1: Build Svelte dashboard ----
FROM node:20-slim AS dashboard-builder

WORKDIR /build/dashboard
COPY dashboard/package.json dashboard/package-lock.json* ./
RUN npm ci

COPY dashboard/ ./
RUN npm run build


# ---- Stage 2: Runtime image ----
FROM python:3.11-slim

# System deps for OpenCV + serial + evdev (evdev needs linux headers + gcc to build from source)
# picotool + libusb-1.0-0: lets the dashboard's "Flash Firmware" button reset
# the RP2040 into BOOTSEL over USB (no physical button press) and reflash it.
# git: lets the System tab's Version card read the checked-out commit from
# the read-only /opt/redwing mount (see daemon/sysinfo.py) — the base image
# doesn't include it.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    udev \
    build-essential \
    linux-libc-dev \
    picotool \
    libusb-1.0-0 \
    git \
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
    "websockets>=12.0" \
    "evdev>=1.6" \
    "rplidar-roboticia" \
    "smbus2"

# Install the redwing library itself
COPY redwing/ ./redwing/
RUN pip install --no-cache-dir -e .

# Copy daemon
COPY daemon/ ./daemon/

# Copy built dashboard static files from stage 1
COPY --from=dashboard-builder /build/dashboard/dist ./dashboard/dist

# Persistent student workspace is bind-mounted at runtime (see docker-compose.yml)
RUN mkdir -p /workspace

# Entrypoint creates /dev/video* nodes from the host's read-only /dev mount,
# then execs the daemon.  This makes the camera truly optional at runtime.
COPY docker/entrypoint-daemon.sh /usr/local/bin/entrypoint-daemon.sh
RUN chmod +x /usr/local/bin/entrypoint-daemon.sh

EXPOSE 8080

ENTRYPOINT ["/usr/local/bin/entrypoint-daemon.sh"]
