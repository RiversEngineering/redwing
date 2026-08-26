#!/bin/bash
# Redwing robotics platform — complete first-time setup for Raspberry Pi.
#
# Download and run:
#   curl -fsSL -o install.sh https://raw.githubusercontent.com/RiversEngineering/redwing/main/install.sh
#   bash install.sh
#
# (No chmod +x needed — `bash install.sh` has bash read and interpret the
# file directly, rather than relying on the OS exec mechanism, which is the
# only path that actually checks the executable bit. That only matters if
# you run it as ./install.sh instead.)
#
# To install a specific branch instead of main (e.g. to test changes before
# merging), download that branch's installer instead and set REDWING_BRANCH
# to the same branch — the "refs/heads/" in the raw URL is required for
# branch names that contain slashes. For example, to install a branch named
# my/branch:
#   curl -fsSL -o install.sh \
#     https://raw.githubusercontent.com/RiversEngineering/redwing/refs/heads/my/branch/install.sh
#   REDWING_BRANCH=my/branch bash install.sh
#
# Safe to re-run — all steps are idempotent.

set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

REPO_URL="https://github.com/RiversEngineering/redwing"
REPO_BRANCH="${REDWING_BRANCH:-main}"
INSTALL_DIR="/opt/redwing"
SERVICE_NAME="redwing"
NEED_REBOOT=0   # set to 1 by steps whose changes only apply after a reboot

# ── Colour helpers ────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; BOLD='\033[1m'; NC='\033[0m'
step() { echo -e "\n${BOLD}[$(date +%H:%M:%S)]${NC} $*"; }
warn() { echo -e "  ${YELLOW}warn:${NC} $*"; }
die()  { echo -e "  ${RED}error:${NC} $*" >&2; exit 1; }
ok()   { echo -e "  ${GREEN}ok:${NC} $*"; }

# A freshly-imaged Pi often has apt-daily/unattended-upgrades or first-boot
# setup services touching dpkg right after boot. If one of those is killed
# mid-operation (e.g. rebooted too early), dpkg is left "interrupted" and
# every apt command fails until `dpkg --configure -a` is run; if one is still
# running, apt-get just needs a moment for the lock to clear. Retry through
# both cases instead of failing the whole install on a transient race.
apt_get() {
    local attempt
    for attempt in 1 2 3; do
        if sudo apt-get "$@"; then
            return 0
        fi
        warn "apt-get $1 failed (attempt $attempt/3) — repairing package state and retrying..."
        sudo dpkg --configure -a || true
        sleep 5
    done
    sudo apt-get "$@"
}

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

# ── 0. Passwordless sudo ───────────────────────────────────────────────────────
# Fresh Raspberry Pi OS images normally set this up automatically for the
# first user, but not every board that reaches this script got here that way
# (reused SD cards, older images, accounts created some other path) — a few
# robots in this fleet needed it added by hand before Ansible could reach
# them non-interactively (there's no human around to type a sudo password
# when a deploy is triggered remotely). Idempotent, and everything below this
# depends on it: if you're piping this script (`curl ... | bash`), there's no
# terminal attached for sudo to prompt on, so a board missing this can't get
# past the very next step regardless — run it locally instead
# (`bash install.sh`) on a board that needs a password typed once.
step "Ensuring passwordless sudo for $INSTALL_USER..."
if sudo -n true 2>/dev/null; then
    ok "Already passwordless"
else
    sudo install -m 0440 -o root -g root /dev/stdin /etc/sudoers.d/010-redwing-nopasswd <<EOF
${INSTALL_USER} ALL=(ALL) NOPASSWD: ALL
EOF
    ok "Configured passwordless sudo for $INSTALL_USER"
fi

# ── 1. System update ──────────────────────────────────────────────────────────
step "Updating system packages..."
sudo dpkg --configure -a || true
apt_get update -q
apt_get upgrade -y -q
ok "System up to date"

# ── 2. Prerequisites ──────────────────────────────────────────────────────────
step "Installing prerequisites..."
apt_get install -y --no-install-recommends \
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
    apt_get install -y docker-compose-plugin
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
# OpenCV/AprilTag script — can transiently exceed 2 GB of RAM, and without swap
# a spike lets the OOM killer take a process. A compressed in-RAM swap device
# (zram) gives a large safety margin for a few % CPU and no SD-card wear.
#
# Raspberry Pi OS already provides zram swap out of the box via
# systemd-zram-generator (the "rpi-swap" units). We rely on that rather than
# installing zram-tools: a second provider claiming the same /dev/zram0
# conflicts and fails at boot with "device busy". So remove zram-tools if an
# earlier install added it, and only provision zram natively if this image
# happens to ship without any zram swap.
step "Ensuring zram swap..."
if dpkg -s zram-tools >/dev/null 2>&1; then
    sudo systemctl disable --now zramswap 2>/dev/null || true
    sudo systemctl reset-failed zramswap 2>/dev/null || true
    apt_get purge -y zram-tools >/dev/null 2>&1 || true
    ok "Removed conflicting zram-tools (Pi OS provides zram natively)"
fi
if swapon --show | grep -q zram; then
    ok "zram swap active ($(swapon --show | awk '/zram/ {print $3; exit}'))"
else
    apt_get install -y --no-install-recommends systemd-zram-generator
    sudo tee /etc/systemd/zram-generator.conf > /dev/null <<'EOF'
# Managed by Redwing — compressed in-RAM swap via systemd-zram-generator.
[zram0]
zram-size = ram
compression-algorithm = zstd
swap-priority = 100
EOF
    ok "Configured zram via systemd-zram-generator (active after reboot)"
fi

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

    # A mem_reservation is only enforced if the kernel memory cgroup controller
    # is enabled. Raspberry Pi OS ships it OFF by default, so Docker silently
    # discards the reservation ("memory soft limit ... Limitation discarded")
    # until these flags are added to the boot cmdline. Takes effect on reboot.
    CGROUP_CMDLINE=/boot/firmware/cmdline.txt
    [[ -f "$CGROUP_CMDLINE" ]] || CGROUP_CMDLINE=/boot/cmdline.txt
    if [[ -f "$CGROUP_CMDLINE" ]] && ! grep -q "cgroup_enable=memory" "$CGROUP_CMDLINE"; then
        # cmdline.txt is a single line; append the flags to it in place.
        sudo sed -i 's/$/ cgroup_enable=memory cgroup_memory=1/' "$CGROUP_CMDLINE"
        NEED_REBOOT=1
        ok "Enabled kernel memory cgroup in $CGROUP_CMDLINE (reboot required)"
    elif [[ -f "$CGROUP_CMDLINE" ]]; then
        ok "Kernel memory cgroup already enabled"
    else
        warn "cmdline.txt not found — enable the memory cgroup manually or mem_reservation is ignored"
    fi
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
if [[ "$NEED_REBOOT" -eq 1 ]]; then
    echo -e "  ${YELLOW}The kernel memory cgroup was just enabled — the daemon's memory"
    echo -e "  reservation is NOT active until you reboot.${NC}"
fi
echo ""

# Only prompt if stdin is a terminal (not piped from curl)
if [[ -t 0 ]]; then
    read -rp "Reboot now? [y/N] " _REBOOT
    [[ "$_REBOOT" =~ ^[Yy]$ ]] && sudo reboot
else
    echo "Run 'sudo reboot' to complete setup."
fi
