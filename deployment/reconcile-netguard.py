"""Reconnect running CPM services whose netguard has acquired a new network namespace."""
import os
from pathlib import Path
import subprocess

GUARDS = {"icpm-caddy-net", "icpm-web-net", "pcpm-caddy-net", "pcpm-web-net", "tailscale-net"}
FORMAT = ('{{.Id}} {{index .Config.Labels "com.docker.compose.service"}} '
          '{{.HostConfig.NetworkMode}} {{.State.Pid}} '
          '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}')


def inspect_containers(identifiers):
    result = subprocess.run(["docker", "inspect", "--format", FORMAT, *identifiers],
                            capture_output=True, text=True)
    # Docker can return partial results when a container disappears during inspection.
    for line in result.stdout.splitlines():
        identifier, service, network, pid, health = line.split()
        try:
            namespace = os.readlink(Path("/proc") / pid / "ns/net")
        except FileNotFoundError:
            continue
        yield identifier, service, network, namespace, health


def reconcile():
    identifiers = subprocess.check_output(
        ["docker", "ps", "-q", "--filter", "label=com.docker.compose.project=cpm"], text=True
    ).split()
    if not identifiers:
        return
    containers = list(inspect_containers(identifiers))
    # Restore the metrics transport and listener before slower auxiliary services.
    containers.sort(key=lambda state: state[1] not in {"tailscale", "pcpm-anubis"})
    guards = {state[0]: state for state in containers if state[1] in GUARDS}
    for identifier, service, network, namespace, _ in containers:
        guard = guards.get(network.removeprefix("container:"))
        if not guard or guard[4] != "healthy" or namespace == guard[3]:
            continue
        # A concurrent stop or replacement invalidates this observation.
        if next(inspect_containers([guard[0]]), None) != guard:
            continue
        current = next(inspect_containers([identifier]), None)
        if not current or current[2:4] != (network, namespace):
            continue
        if subprocess.run(["systemctl", "is-active", "--quiet", "cpm.service"]).returncode:
            return
        print(f"Reconnecting {service} to {guard[1]}", flush=True)
        subprocess.run(["docker", "restart", identifier], check=True)


if __name__ == "__main__":
    reconcile()
