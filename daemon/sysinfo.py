"""One-off system identity info for the System tab: network address and the
git commit currently checked out.

Unlike sysmon.py's periodic resource sampling, none of this changes during a
run — hostname/IP are essentially fixed for a robot's Pi for the life of a
session, and the git commit is fixed until the daemon is rebuilt and
restarted — so it's computed once at startup rather than polled.
"""

import logging
import socket
import subprocess

log = logging.getLogger(__name__)

# Read-only bind mount of the repo root — see docker-compose.yml. Root (this
# container's user) accessing a directory owned by another uid (the host
# user who cloned the repo) trips git's "dubious ownership" safety check
# (CVE-2022-24765) unless explicitly trusted — passed per-call rather than
# via a persisted --global config so this doesn't depend on $HOME state.
_REPO_ROOT = "/opt/redwing"
_GIT_ARGS = ["-c", f"safe.directory={_REPO_ROOT}", "-C", _REPO_ROOT]


def get_network_info() -> dict:
    """Hostname and primary LAN IP. network_mode: host (see docker-compose.yml)
    means these reflect the actual Pi, not a container-private namespace.
    """
    hostname = socket.gethostname()
    ip = None
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Doesn't actually send any packets — connect() on a UDP socket just
        # picks the local interface/address the kernel would route through.
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except OSError:
        pass
    finally:
        s.close()
    return {"hostname": hostname, "ip": ip}


def get_version_info() -> dict:
    """Short commit hash and commit date of the checked-out /opt/redwing."""
    def _git(*args) -> str | None:
        try:
            result = subprocess.run(
                ["git", *_GIT_ARGS, *args],
                capture_output=True, text=True, timeout=5,
            )
            return result.stdout.strip() or None
        except (OSError, subprocess.SubprocessError) as e:
            log.warning(f"sysinfo: git {' '.join(args)} failed: {e}")
            return None

    return {
        "commit": _git("rev-parse", "--short", "HEAD"),
        "date":   _git("log", "-1", "--format=%cI"),
    }
