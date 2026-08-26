#!/bin/bash
# Refresh the .local -> IP mappings the dnsmasq bridge serves to Docker.
#
# mDNS has no "list everyone" query — each known robot hostname has to be
# resolved individually via the host's own Avahi. Run periodically by
# mdns-hosts-refresh.timer (installed separately, see ../../README.md); safe
# to run manually too.
#
# A robot that fails to resolve this round is simply dropped from the file
# rather than kept at its last-known IP — if it's actually offline, "can't
# resolve" is the honest answer; serving a stale cached IP risks pointing at
# whatever device the DHCP pool handed that address to next.

set -euo pipefail

INVENTORY=/home/pi/redwing/ansible/inventory.yml
OUT=/etc/dnsmasq.d/redwing-mdns-hosts.conf

names=$(grep -oE '[A-Za-z0-9_-]+\.local' "$INVENTORY" | sort -u || true)

tmp=$(mktemp)
trap 'rm -f "$tmp"' EXIT

for name in $names; do
    ip=$(avahi-resolve -4 -n "$name" 2>/dev/null | awk '{print $2}') || ip=""
    if [[ -n "$ip" ]]; then
        echo "host-record=$name,$ip" >> "$tmp"
    fi
done

if ! cmp -s "$tmp" "$OUT" 2>/dev/null; then
    cp "$tmp" "$OUT"
    systemctl reload dnsmasq
fi
