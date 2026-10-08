# syntax=docker/dockerfile:1
#
# Build speed notes: the RUN --mount=type=cache lines keep apt/pip/npm
# downloads in BuildKit's cache between builds, so editing a package list
# re-installs but doesn't re-download everything. apt's docker-clean hook
# (which deletes downloaded .debs) is removed so the apt cache actually fills.

# ---- Stage 1: Build Svelte dashboard ----
FROM node:20-slim AS dashboard-builder

WORKDIR /build/dashboard
COPY dashboard/package.json dashboard/package-lock.json* ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci

COPY dashboard/ ./
RUN npm run build


# ---- Stage 2: Build Python wheels ----
# Compilers live only in this stage. Anything without a prebuilt wheel for
# this platform (notably evdev, which is sdist-only) is compiled here, and the
# runtime stage installs the finished wheels — so the runtime image doesn't
# need build-essential / linux-libc-dev.
FROM python:3.11-slim AS wheel-builder

RUN rm -f /etc/apt/apt.conf.d/docker-clean \
    && echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' > /etc/apt/apt.conf.d/keep-cache
RUN --mount=type=cache,id=apt-cache-daemon,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,id=apt-lists-daemon,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    linux-libc-dev

RUN --mount=type=cache,target=/root/.cache/pip \
    pip wheel --wheel-dir /wheels \
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


# ---- Stage 3: Runtime image ----
FROM python:3.11-slim

# System deps for OpenCV + serial
# picotool + libusb-1.0-0: lets the dashboard's "Flash Firmware" button reset
# the RP2040 into BOOTSEL over USB (no physical button press) and reflash it.
# git: lets the System tab's Version card read the checked-out commit from
# the read-only /opt/redwing mount (see daemon/sysinfo.py) — the base image
# doesn't include it.
RUN rm -f /etc/apt/apt.conf.d/docker-clean \
    && echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' > /etc/apt/apt.conf.d/keep-cache
RUN --mount=type=cache,id=apt-cache-daemon,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,id=apt-lists-daemon,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    udev \
    picotool \
    libusb-1.0-0 \
    git

WORKDIR /app

# Install Python dependencies from the wheels built in stage 2. The bind
# mount means the wheel files themselves never end up in an image layer.
RUN --mount=type=bind,from=wheel-builder,source=/wheels,target=/wheels \
    pip install --no-cache-dir --no-index /wheels/*.whl

# Install the redwing library itself
COPY pyproject.toml ./
COPY redwing/ ./redwing/
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -e .

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
