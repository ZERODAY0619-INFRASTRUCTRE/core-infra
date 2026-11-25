"""Reconnect running CPM services whose netguard has acquired a new network namespace."""
import os
from pathlib import Path
import subprocess

GUARDS = {"icpm-caddy-net", "icpm-web-net", "pcpm-caddy-net", "pcpm-web-net", "tailscale-net"}
FORMAT = ('{{.Id}} {{index .Config.Labels "com.docker.compose.service"}} '
          '{{.HostConfig.NetworkMode}} {{.State.Pid}} '
          '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}')


def inspect_container(container):
    result = subprocess.run(["docker", "inspect", "--format", FORMAT, container],
                            capture_output=True, text=True)
    if result.returncode:
        return None
    identifier, service, network, pid, health = result.stdout.split()
    try:
        namespace = os.readlink(Path("/proc") / pid / "ns/net")
    except FileNotFoundError:
        return None
    return identifier, service, network, namespace, health


def reconcile():
    identifiers = subprocess.check_output(
        ["docker", "ps", "-q", "--filter", "label=com.docker.compose.project=cpm"], text=True
    ).split()
    containers = [state for identifier in identifiers if (state := inspect_container(identifier))]
    guards = {state[0]: state for state in containers if state[1] in GUARDS}
    for identifier, service, network, namespace, _ in containers:
        guard = guards.get(network.removeprefix("container:"))
        if not guard or guard[4] != "healthy" or namespace == guard[3]:
            continue
        # A concurrent stop or replacement invalidates this observation.
        if inspect_container(guard[0]) != guard:
            continue
        current = inspect_container(identifier)
        if not current or current[2:4] != (network, namespace):
            continue
        if subprocess.run(["systemctl", "is-active", "--quiet", "cpm.service"]).returncode:
            return
        print(f"Reconnecting {service} to {guard[1]}", flush=True)
        subprocess.run(["docker", "restart", identifier], check=True)


if __name__ == "__main__":
    reconcile()
