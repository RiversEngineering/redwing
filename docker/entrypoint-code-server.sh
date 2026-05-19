#!/bin/sh
set -e
chown -R coder:coder /home/coder/project 2>/dev/null || true
exec gosu coder code-server --bind-addr 0.0.0.0:8080 /home/coder/project
