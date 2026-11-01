"""Fixed operations on the personal host. Nothing in the HTTP request becomes a command."""

import json
import os
import subprocess
from pathlib import Path


def perform(action, fingerprint, pin):
    def run(args, timeout=7):
        return subprocess.run(
            args, capture_output=True, text=True, timeout=timeout, check=True
        ).stdout.strip()

    if (
        os.geteuid() != 0
        or fingerprint not in run(["ssh-keygen", "-lf", "/etc/ssh/ssh_host_ed25519_key.pub"]).split()
    ):
        return {"result": "identity_mismatch"}
    name = "jp-proxy-mihomo-1"
    obj = json.loads(run(["docker", "inspect", name]))[0]
    labels = obj["Config"]["Labels"]
    if (
        labels.get("com.docker.compose.project") != "jp-proxy"
        or labels.get("com.docker.compose.service") != "mihomo"
    ):
        return {"result": "identity_mismatch"}
    healthy = obj["State"].get("Health", {}).get("Status") == "healthy"
    image = obj["Config"]["Image"]
    current = image.split("@")[-1] == pin and image.split("@")[0] in (
        "metacubex/mihomo",
        "docker.io/metacubex/mihomo",
    )
    if action == "status":
        available_kib = int(
            next(
                line.split()[1]
                for line in Path("/proc/meminfo").read_text().splitlines()
                if line.startswith("MemAvailable:")
            )
        )
        return {
            "result": "online",
            "healthy": healthy,
            "pinned": current,
            "restarts": obj["RestartCount"],
            "started": obj["State"]["StartedAt"][:19] + "Z",
            "memory_available_mib": available_kib // 1024,
        }
    if action == "update" and current:
        return {"result": "current"}
    if action == "restart":
        if not healthy or not current:
            return {"result": "preflight_failed"}
        # Reuse the existing immutable container. Transient job survives loss of the console.
        run(
            [
                "systemd-run",
                "--unit=relay-owner-core-restart",
                "--collect",
                "--on-active=3s",
                "--timer-property=AccuracySec=1s",
                "/usr/bin/docker",
                "restart",
                "--time",
                "10",
                obj["Id"],
            ]
        )
        return {"result": "restart_scheduled"}
    if action == "update":
        # An independently staged, host-owned unit must include its own acceptance and rollback.
        unit = "relay-apply-approved.service"
        if not healthy or run(["systemctl", "show", "-p", "LoadState", "--value", unit]) != "loaded":
            return {"result": "needs_staging"}
        if run(["systemctl", "show", "-p", "ActiveState", "--value", unit]) in ("active", "activating"):
            return {"result": "busy"}
        run(["systemctl", "start", "--no-block", unit])
        return {"result": "update_scheduled"}
    return {"result": "unsupported"}
