#!/bin/sh

# If the project source is mounted, reinstall the library from it so that
# a `git pull` + `docker compose restart code-server` picks up any changes
# without needing a full image rebuild.
if [ -f /opt/redwing/pyproject.toml ]; then
    cp -r /opt/redwing /tmp/redwing_build 2>/dev/null && \
    pip3 install --break-system-packages --no-cache-dir \
        --force-reinstall --no-deps /tmp/redwing_build 2>&1 && \
    echo "[entrypoint] redwing library updated from source" || \
    echo "[entrypoint] WARNING: library reinstall failed, using baked-in version"
    rm -rf /tmp/redwing_build 2>/dev/null
fi

chown -R coder:coder /home/coder/project 2>/dev/null || true
exec gosu coder code-server --bind-addr 0.0.0.0:8080 /home/coder/project
