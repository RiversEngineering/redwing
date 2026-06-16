#!/bin/bash
# Redwing robotics platform — first-time setup for Raspberry Pi.
# Run from the repo root as a normal user (sudo is invoked internally).
#
#   chmod +x install.sh && ./install.sh

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="$REPO_DIR/docker/docker-compose.yml"
SERVICE_NAME="redwing"
CURRENT_USER="${SUDO_USER:-$USER}"

# ── Colour helpers ────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
step()  { echo -e "\n${GREEN}==>${NC} $*"; }
warn()  { echo -e "${YELLOW}warn:${NC} $*"; }
die()   { echo -e "${RED}error:${NC} $*" >&2; exit 1; }

# ── Preflight ─────────────────────────────────────────────────────────────────
[[ "$(uname -m)" =~ ^(aarch64|armv7l)$ ]] || \
    warn "Not running on ARM — this script targets Raspberry Pi."

[[ $EUID -ne 0 ]] || die "Run as a regular user, not root. sudo is called internally."

# ── 1. System packages ────────────────────────────────────────────────────────
step "Updating package lists..."
sudo apt-get update -q

step "Installing system dependencies..."
sudo apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    git \
    i2c-tools \
    python3-smbus

# ── 2. Docker ─────────────────────────────────────────────────────────────────
step "Installing Docker..."
if command -v docker &>/dev/null; then
    echo "  Already installed: $(docker --version)"
else
    curl -fsSL https://get.docker.com | sh
fi

step "Adding $CURRENT_USER to the docker group..."
sudo usermod -aG docker "$CURRENT_USER"

step "Enabling Docker on boot..."
sudo systemctl enable --now docker

# Verify docker compose plugin
if ! docker compose version &>/dev/null; then
    step "Installing docker-compose-plugin..."
    sudo apt-get install -y docker-compose-plugin
fi
echo "  $(docker compose version)"

# ── 3. I²C (battery monitor, VL53L0X, HAT sensors) ───────────────────────────
step "Enabling I²C..."
# raspi-config nonint is the canonical way on all Pi OS versions
if command -v raspi-config &>/dev/null; then
    sudo raspi-config nonint do_i2c 0
    echo "  I²C enabled via raspi-config"
else
    # Fallback: edit config.txt directly
    BOOT_CONFIG=""
    for p in /boot/firmware/config.txt /boot/config.txt; do
        [[ -f "$p" ]] && BOOT_CONFIG="$p" && break
    done
    if [[ -n "$BOOT_CONFIG" ]]; then
        grep -q "^dtparam=i2c_arm=on" "$BOOT_CONFIG" || \
            echo "dtparam=i2c_arm=on" | sudo tee -a "$BOOT_CONFIG"
        echo "  Added dtparam=i2c_arm=on to $BOOT_CONFIG"
    else
        warn "Could not find boot config — enable I²C manually via raspi-config"
    fi
fi

# Load the module now (without reboot) and persist it
sudo modprobe i2c-dev 2>/dev/null || true
grep -q "^i2c-dev" /etc/modules 2>/dev/null || \
    echo "i2c-dev" | sudo tee -a /etc/modules

# ── 4. udev rules (stable /dev/rp2040 symlink) ────────────────────────────────
step "Installing RP2040 udev rules..."
sudo cp "$REPO_DIR/docker/99-rp2040.rules" /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger
echo "  Installed: /etc/udev/rules.d/99-rp2040.rules"

# ── 5. Build Docker images ────────────────────────────────────────────────────
step "Building Docker images (this will take several minutes)..."
# Run docker as the current user in case we're in a sudo context
sudo -u "$CURRENT_USER" docker compose -f "$COMPOSE_FILE" build

# ── 6. Systemd service (auto-start on boot) ───────────────────────────────────
step "Installing redwing systemd service..."
DOCKER_BIN="$(command -v docker)"
sudo tee /etc/systemd/system/${SERVICE_NAME}.service > /dev/null <<EOF
[Unit]
Description=Redwing Robotics Platform
After=docker.service network-online.target
Requires=docker.service

[Service]
Type=simple
User=${CURRENT_USER}
WorkingDirectory=${REPO_DIR}
ExecStart=${DOCKER_BIN} compose -f ${COMPOSE_FILE} up
ExecStop=${DOCKER_BIN} compose -f ${COMPOSE_FILE} down
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable "${SERVICE_NAME}.service"
echo "  Service installed and enabled"

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}Installation complete!${NC}"
echo ""
echo "Next steps:"
echo "  1. Reboot (required for I²C, docker group, and udev rules to take full effect):"
echo "       sudo reboot"
echo ""
echo "  After reboot, Redwing starts automatically. To control it manually:"
echo "       sudo systemctl start redwing     # start"
echo "       sudo systemctl stop  redwing     # stop"
echo "       sudo systemctl status redwing    # check status"
echo "       journalctl -u redwing -f         # live logs"
echo ""
echo "  Dashboard:   http://<pi-ip>:8000"
echo "  Code editor: http://<pi-ip>:8080  (password: redwing)"
