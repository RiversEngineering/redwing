#!/bin/bash
# Trust a new robot with the fleet SSH key so Ansible/Semaphore can reach it.
# Usage: add-robot.sh <ip-or-hostname>

set -euo pipefail

HOST="${1:?Usage: add-robot.sh <ip-or-hostname>}"
KEY="$HOME/.ssh/redwing_key.pub"

if [[ ! -f "$KEY" ]]; then
    echo "Fleet public key not found at $KEY" >&2
    exit 1
fi

ssh-copy-id -i "$KEY" "pi@$HOST"

cat <<EOF

Trusted $HOST with the fleet key. Don't forget to add it to
ansible/inventory.yml, e.g.:

    robot5:
      ansible_host: $HOST

then commit and push so future deploys pick it up.
EOF
