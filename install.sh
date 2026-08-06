#!/bin/bash
# Redwing robotics platform — complete first-time setup for Raspberry Pi.
#
# Run directly or pipe from GitHub:
#   bash <(curl -fsSL https://raw.githubusercontent.com/RiversEngineering/redwing/main/install.sh)
#
# To install a specific branch instead of main (e.g. to test changes before
# merging), download that branch's installer to a file and run it with
# REDWING_BRANCH set to the same branch. Download-then-run works in any shell
# (unlike `bash <(...)`, which needs bash), and the "refs/heads/" in the raw
# URL is required for branch names that contain slashes. For this branch:
#   curl -fsSL -o /tmp/redwing-install.sh \
#     https://raw.githubusercontent.com/RiversEngineering/redwing/refs/heads/claude/robotics-ram-requirements-pk02bv/install.sh
#   REDWING_BRANCH=claude/robotics-ram-requirements-pk02bv bash /tmp/redwing-install.sh
#
# Safe to re-run — all steps are idempotent.

set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

REPO_URL="https://github.com/RiversEngineering/redwing"
REPO_BRANCH="${REDWING_BRANCH:-main}"
INSTALL_DIR="/opt/redwing"
SERVICE_NAME="redwing"

# ── Colour helpers ────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; BOLD='\033[1m'; NC='\033[0m'
step() { echo -e "\n${BOLD}[$(date +%H:%M:%S)]${NC} $*"; }
warn() { echo -e "  ${YELLOW}warn:${NC} $*"; }
die()  { echo -e "  ${RED}error:${NC} $*" >&2; exit 1; }
ok()   { echo -e "  ${GREEN}ok:${NC} $*"; }

# ── Preflight ─────────────────────────────────────────────────────────────────
[[ "$(uname)" == "Linux" ]] || die "This script targets Raspberry Pi OS (Linux)."
[[ "$(uname -m)" =~ ^(aarch64|armv7l)$ ]] || warn "Not running on ARM — intended for Raspberry Pi."

if [[ $EUID -eq 0 ]]; then
    INSTALL_USER="${SUDO_USER:-}"
    [[ -z "$INSTALL_USER" ]] && die "Do not run directly as root.\nUse: bash install.sh  (sudo is called internally)"
else
    INSTALL_USER="$USER"
fi

echo -e "\n${BOLD}Redwing installer${NC}"
echo "  User:    $INSTALL_USER"
echo "  Install: $INSTALL_DIR"
echo "  Repo:    $REPO_URL"
echo "  Branch:  $REPO_BRANCH"

# ── 1. System update ──────────────────────────────────────────────────────────
step "Updating system packages..."
sudo apt-get update -q
sudo apt-get upgrade -y -q
ok "System up to date"

# ── 2. Prerequisites ──────────────────────────────────────────────────────────
step "Installing prerequisites..."
sudo apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    git \
    i2c-tools \
    python3-smbus
ok "Prerequisites installed"

# ── 3. Clone / update repo ────────────────────────────────────────────────────
step "Setting up Redwing repo at $INSTALL_DIR..."
if [[ -d "$INSTALL_DIR/.git" ]]; then
    echo "  Repo already present — updating to '$REPO_BRANCH'..."
    sudo git -C "$INSTALL_DIR" fetch --quiet origin "$REPO_BRANCH"
    sudo git -C "$INSTALL_DIR" checkout --quiet -B "$REPO_BRANCH" "origin/$REPO_BRANCH"
    sudo git -C "$INSTALL_DIR" reset --hard --quiet "origin/$REPO_BRANCH"
    ok "Repo updated to '$REPO_BRANCH'"
else
    sudo git clone --quiet --branch "$REPO_BRANCH" "$REPO_URL" "$INSTALL_DIR"
    ok "Repo cloned ('$REPO_BRANCH')"
fi
sudo chown -R "${INSTALL_USER}:${INSTALL_USER}" "$INSTALL_DIR"

COMPOSE_FILE="$INSTALL_DIR/docker/docker-compose.yml"

# ── 4. Docker ─────────────────────────────────────────────────────────────────
step "Installing Docker..."
if command -v docker &>/dev/null; then
    ok "Already installed: $(docker --version)"
else
    curl -fsSL https://get.docker.com | sh
    ok "Docker installed"
fi

step "Adding $INSTALL_USER to the docker group..."
sudo usermod -aG docker "$INSTALL_USER"
ok "$INSTALL_USER added to docker group"

step "Enabling Docker service..."
sudo systemctl enable --now docker
ok "Docker enabled"

if ! docker compose version &>/dev/null 2>&1; then
    step "Installing docker-compose-plugin..."
    sudo apt-get install -y docker-compose-plugin
fi
ok "$(docker compose version)"

# ── 5. I²C (battery monitor, HAT sensors, VL53L0X ToF) ───────────────────────
step "Enabling I²C interface..."
if command -v raspi-config &>/dev/null; then
    sudo raspi-config nonint do_i2c 0
    ok "I²C enabled via raspi-config"
else
    BOOT_CONFIG=""
    for p in /boot/firmware/config.txt /boot/config.txt; do
        [[ -f "$p" ]] && BOOT_CONFIG="$p" && break
    done
    if [[ -n "$BOOT_CONFIG" ]]; then
        grep -q "^dtparam=i2c_arm=on" "$BOOT_CONFIG" || \
            echo "dtparam=i2c_arm=on" | sudo tee -a "$BOOT_CONFIG" > /dev/null
        ok "dtparam=i2c_arm=on added to $BOOT_CONFIG"
    else
        warn "Cannot locate boot config — enable I²C manually with raspi-config and rerun"
    fi
fi
# Load the kernel module now (no reboot needed for this session) and persist it
sudo modprobe i2c-dev 2>/dev/null || true
grep -q "^i2c-dev" /etc/modules 2>/dev/null || \
    echo "i2c-dev" | sudo tee -a /etc/modules > /dev/null

# ── 5a. zram swap (memory headroom for 2 GB Pi 4 boards) ──────────────────────
# The full stack — code-server + Pylance, the vision daemon, and a student's own
# OpenCV/AprilTag script — can transiently exceed 2 GB of RAM. Without swap a
# spike is fatal (the OOM killer takes a process). zram gives a compressed
# in-RAM swap device (zstd ~3-4x) for a few % CPU and no SD-card wear. Harmless
# on 4 GB boards, which simply never touch it.
step "Configuring zram swap..."
sudo apt-get install -y --no-install-recommends zram-tools
sudo tee /etc/default/zramswap > /dev/null <<'EOF'
# Managed by Redwing install.sh — compressed in-RAM swap.
ALGO=zstd
# zram device size as a percentage of physical RAM. On a 2 GB Pi this allocates
# a ~2 GB swap device that costs far less actual RAM once compressed; on a 4 GB
# Pi it is available but rarely used.
PERCENT=100
PRIORITY=100
EOF
sudo systemctl enable --now zramswap 2>/dev/null || sudo systemctl restart zramswap || \
    warn "zramswap service not available — check 'zramctl' after reboot"
ok "zram swap configured"

# ── 5b. Nintendo Switch controller support (hid-nintendo) ─────────────────────
# Required for the GameSir Nova Lite (and any Switch-mode controller) to be
# recognised as a gamepad by evdev. Without it, hid-generic handles the device
# but produces no standard gamepad events.
step "Enabling hid-nintendo kernel module..."
sudo modprobe hid-nintendo 2>/dev/null || warn "hid-nintendo not available on this kernel (may need kernel update)"
grep -q "^hid-nintendo" /etc/modules 2>/dev/null || \
    echo "hid-nintendo" | sudo tee -a /etc/modules > /dev/null
ok "hid-nintendo enabled"

# ── 6. udev rules (stable /dev/rp2040 symlink for RP2040) ─────────────────────
step "Installing udev rules..."
sudo cp "$INSTALL_DIR/docker/99-rp2040.rules" /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger
ok "/etc/udev/rules.d/99-rp2040.rules installed"

# ── 7. Build / pull Docker images ────────────────────────────────────────────
step "Pulling pre-built Docker images (nginx…)..."
sudo docker compose -f "$COMPOSE_FILE" pull --ignore-buildable
ok "Images pulled"

step "Building Docker images..."
echo "  (This takes ~10 min on a Pi 4, ~5 min on a Pi 5 — please wait)"
sudo docker compose -f "$COMPOSE_FILE" build
ok "Images built"

# ── 8. Systemd service (auto-start on boot) ───────────────────────────────────
step "Installing redwing systemd service..."
DOCKER_BIN="$(command -v docker)"

# Give the robot daemon a soft memory-protection floor on low-RAM boards so the
# camera feed / control loop survive memory pressure (see mem_reservation in
# docker-compose.yml). Only applied on <=2 GB boards (Pi 4); 4 GB boards (Pi 5)
# have plenty of headroom and get 0 (no reservation).
MEM_TOTAL_KB="$(awk '/^MemTotal:/ {print $2}' /proc/meminfo 2>/dev/null || echo 0)"
if [[ "$MEM_TOTAL_KB" -gt 0 && "$MEM_TOTAL_KB" -le 2621440 ]]; then   # <= 2.5 GiB
    DAEMON_MEM_RESERVATION="384m"
    ok "Low-RAM board detected (${MEM_TOTAL_KB} kB) — daemon mem_reservation=${DAEMON_MEM_RESERVATION}"
else
    DAEMON_MEM_RESERVATION="0"
    ok "Board has ample RAM (${MEM_TOTAL_KB} kB) — no daemon mem_reservation"
fi

sudo tee /etc/systemd/system/${SERVICE_NAME}.service > /dev/null <<EOF
[Unit]
Description=Redwing Robotics Platform
After=docker.service network-online.target
Requires=docker.service

[Service]
Type=simple
WorkingDirectory=${INSTALL_DIR}
Environment=REDWING_DAEMON_MEM_RESERVATION=${DAEMON_MEM_RESERVATION}
ExecStart=${DOCKER_BIN} compose -f ${COMPOSE_FILE} up
ExecStop=${DOCKER_BIN} compose -f ${COMPOSE_FILE} down
Restart=on-failure
RestartSec=10
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable "${SERVICE_NAME}.service"
ok "redwing.service installed and enabled"

# ── Done ──────────────────────────────────────────────────────────────────────
PI_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"

echo ""
echo -e "${BOLD}${GREEN}Installation complete!${NC}"
echo ""
echo "  Manage the service:"
echo "    sudo systemctl start   redwing"
echo "    sudo systemctl stop    redwing"
echo "    sudo systemctl restart redwing"
echo "    journalctl -u redwing -f        # live logs"
echo ""
echo "  After reboot:"
echo "    Landing page: http://${PI_IP}"
echo "    Dashboard:    http://${PI_IP}/dashboard"
echo "    Code editor:  http://${PI_IP}/editor  (password: redwing)"
echo ""
echo "  A reboot is required for I²C and docker group changes to take full effect."
echo ""

# Only prompt if stdin is a terminal (not piped from curl)
if [[ -t 0 ]]; then
    read -rp "Reboot now? [y/N] " _REBOOT
    [[ "$_REBOOT" =~ ^[Yy]$ ]] && sudo reboot
else
    echo "Run 'sudo reboot' to complete setup."
fi
