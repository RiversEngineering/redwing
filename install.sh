#!/bin/bash
# Redwing robotics platform — complete first-time setup for Raspberry Pi.
#
# Run directly or pipe from GitHub:
#   bash <(curl -fsSL https://raw.githubusercontent.com/RiversEngineering/redwing/main/install.sh)
#
# Safe to re-run — all steps are idempotent.

set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

REPO_URL="https://github.com/RiversEngineering/redwing"
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
    echo "  Repo already present — pulling latest..."
    sudo git -C "$INSTALL_DIR" fetch --quiet
    sudo git -C "$INSTALL_DIR" reset --hard origin/main --quiet
    ok "Repo updated"
else
    sudo git clone --quiet "$REPO_URL" "$INSTALL_DIR"
    ok "Repo cloned"
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

# ── 6. udev rules (stable /dev/rp2040 symlink for RP2040) ─────────────────────
step "Installing udev rules..."
sudo cp "$INSTALL_DIR/docker/99-rp2040.rules" /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger
ok "/etc/udev/rules.d/99-rp2040.rules installed"

# ── 7. Build Docker images ────────────────────────────────────────────────────
step "Building Docker images..."
echo "  (This takes ~10 min on a Pi 4, ~5 min on a Pi 5 — please wait)"
sudo docker compose -f "$COMPOSE_FILE" build
ok "Images built"

# ── 8. Systemd service (auto-start on boot) ───────────────────────────────────
step "Installing redwing systemd service..."
DOCKER_BIN="$(command -v docker)"

sudo tee /etc/systemd/system/${SERVICE_NAME}.service > /dev/null <<EOF
[Unit]
Description=Redwing Robotics Platform
After=docker.service network-online.target
Requires=docker.service

[Service]
Type=simple
WorkingDirectory=${INSTALL_DIR}
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
echo "    Dashboard:   http://${PI_IP}:8000"
echo "    Code editor: http://${PI_IP}:8080  (password: redwing)"
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
