#!/usr/bin/env python3
"""Read-only Compose contract and nft syntax checks; never print secrets."""
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent

def run(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout

def validate_live_namespaces(services):
    """Catch healthy sidecars still attached to a replaced guard container."""
    ids = run("docker", "compose", "-f", str(ROOT / "compose.yaml"),
              "ps", "--all", "--quiet").split()
    assert ids, "No deployed containers found"
    containers = json.loads(run("docker", "inspect", *ids))
    deployed = {c["Config"]["Labels"]["com.docker.compose.service"]: c for c in containers}
    for name, service in services.items():
        target = service.get("network_mode", "")
        if not target.startswith("service:"):
            continue
        guard_name = target.removeprefix("service:")
        assert name in deployed and guard_name in deployed, f"Missing deployed service: {name} or {guard_name}"
        app, guard = deployed[name], deployed[guard_name]
        assert app["State"]["Running"] and guard["State"]["Running"], f"Stopped namespace dependency: {name}"
        assert app["HostConfig"]["NetworkMode"] == "container:" + guard["Id"], f"Stale network namespace: {name} must be recreated with {guard_name}"
        print(f"PASS: live namespace {name} -> {guard_name}")
    for prefix in ("icpm", "pcpm"):
        if prefix + "-clickhouse" not in services:
            continue
        run("docker", "exec", deployed[prefix + "-web"]["Id"], "bun", "-e",
            "fetch('http://127.0.0.1:8123/ping',{signal:AbortSignal.timeout(5000)})"
            ".then(async r=>process.exit(r.ok&&(await r.text()).trim()==='Ok.'?0:1))"
            ".catch(()=>process.exit(1))")
        print(f"PASS: {prefix} web can reach ClickHouse")

def main():
    sys.path.insert(0, str(ROOT / "scripts"))
    from site_config import settings, render
    site = settings(ROOT / ".env")
    render(site, ROOT / "deployment/generated")
    config = json.loads(run("docker", "compose", "-f", str(ROOT / "compose.yaml"),
                            "config", "--format", "json"))
    services = config["services"]
    analytics = {name for name in services if name.endswith("-clickhouse")}
    assert analytics <= {"icpm-clickhouse", "pcpm-clickhouse"}
    geoip = {name for name in services if name.endswith("-geoipupdate")}
    assert geoip <= {"icpm-geoipupdate", "pcpm-geoipupdate"}
    assert len(services) == 13 + len(analytics) + len(geoip), "Unexpected service count"
    # Public SSO issuer and the two narrowly scoped TLS paths must move together.
    sso_host = site["SSO_HOST"]
    for prefix, address in (("icpm", site["PUBLIC_BIND_IP"]), ("pcpm", "172.30.81.2")):
        assert services[prefix + "-web"]["environment"]["OAUTH_ISSUER"] == f"https://{sso_host}/application/o/{prefix}/"
        assert f"{sso_host}={address}" in services[prefix + "-web-net"]["extra_hosts"]
        policy = (ROOT / "deployment/generated/policy" / f"{prefix}-web.nft").read_text()
        assert f"ip daddr {address} tcp dport 443 accept" in policy
    secrets = []
    expected = {
        "icpm-caddy-net": set(),
        "tailscale-net": set(),
        "pcpm-caddy-net": {(site["PUBLIC_BIND_IP"], 80, 80), (site["PUBLIC_BIND_IP"], 443, 443)},
        "icpm-web-net": set(),
        "pcpm-web-net": set(),
    }
    for name, service in services.items():
        assert service["restart"] == "no", "Restart can bypass health gates"
        assert not service.get("privileged")
        assert not any("docker.sock" in v.get("source", "") for v in service.get("volumes", []))
        if name.endswith("-net"):
            actual = {(p["host_ip"], int(p["published"]), int(p["target"])) for p in service.get("ports", [])}
            assert actual == expected[name], f"Unexpected port on {name}"
            assert all(p["protocol"] == "tcp" for p in service.get("ports", []))
            assert set(service["cap_add"]) == {"NET_ADMIN"}
            if name != "tailscale-net":
                assert service["depends_on"]["tailscale"]["condition"] == "service_healthy"
                assert service["environment"]["TAILNET_GATEWAY"] in {"172.30.80.4", "172.30.81.4"}
        elif name == "tailscale":
            assert not service.get("ports") and not service.get("networks")
            assert service["network_mode"] == "service:tailscale-net"
            assert set(service["cap_add"]) == {"NET_ADMIN", "NET_RAW"}
            assert service["depends_on"]["tailscale-net"]["condition"] == "service_healthy"
            assert service["environment"]["TS_USERSPACE"] == "false"
            assert "--netfilter-mode=off" in service["environment"]["TS_EXTRA_ARGS"]
            assert "--advertise-exit-node=false" in service["environment"]["TS_EXTRA_ARGS"]
            if not service["environment"].get("TS_AUTHKEY"):
                print("NOTE: Fill TS_AUTHKEY in the root .env before first start.")
        elif name == "pcpm-authentik-relay":
            assert not service.get("ports") and not service.get("networks")
            assert not service.get("cap_add")
            assert set(service["cap_drop"]) == {"ALL"}
            assert service["network_mode"] == "service:pcpm-caddy-net"
            assert service["read_only"]
            assert service["depends_on"]["pcpm-caddy-net"]["condition"] == "service_healthy"
            assert service["command"] == ["caddy", "run", "--config", "/etc/caddy/authentik-outpost.Caddyfile", "--adapter", "caddyfile"]
            assert len(service["volumes"]) == 1 and service["volumes"][0]["read_only"]
            assert services["pcpm-web"]["depends_on"][name]["condition"] == "service_healthy"
        elif name == "pcpm-feedback":
            assert not service.get("ports") and not service.get("networks")
            assert not service.get("cap_add")
            assert set(service["cap_drop"]) == {"ALL"}
            assert service["network_mode"] == "service:pcpm-caddy-net"
            assert service["read_only"]
            assert service["entrypoint"] == ["bun", "/feedback/server.ts"]
            assert service["environment"]["ERROR_FEEDBACK_PATH"] == "/app/feedback/error-feedback.db"
            assert service["depends_on"]["pcpm-caddy-net"]["condition"] == "service_healthy"
            assert len(service["volumes"]) == 4
            assert all(v.get("read_only") for v in service["volumes"] if v["type"] == "bind")
            assert services["pcpm-web"]["environment"]["CPM_FEEDBACK_UPSTREAM"] == "127.0.0.1:8930"
            assert services["pcpm-web"]["depends_on"][name]["condition"] == "service_healthy"
        elif name == "pcpm-anubis":
            assert not service.get("ports") and not service.get("networks")
            assert not service.get("cap_add")
            assert set(service["cap_drop"]) == {"ALL"}
            assert service["network_mode"] == "service:pcpm-caddy-net"
            assert service["read_only"]
            assert service["depends_on"]["pcpm-caddy-net"]["condition"] == "service_healthy"
            assert service["environment"]["BIND"] == "127.0.0.1:8923"
            assert service["environment"]["TARGET"] == "http://127.0.0.1:8924"
            assert re.fullmatch(r"[0-9a-f]{64}", service["environment"]["ED25519_PRIVATE_KEY_HEX"])
            assert all(v["read_only"] for v in service["volumes"])
            assert services["pcpm-web"]["depends_on"][name]["condition"] == "service_healthy"
            assert services["pcpm-web"]["environment"]["ANUBIS_PROTECTED_DOMAIN"] == site["ANUBIS_PROTECTED_DOMAIN"]
        elif name.endswith("-geoipupdate"):
            prefix = name.removesuffix("-geoipupdate")
            assert not service.get("ports") and not service.get("network_mode")
            assert not service.get("cap_add")
            assert set(service["cap_drop"]) == {"ALL"}
            assert "no-new-privileges:true" in service["security_opt"]
            assert set(service["networks"]) == {"geoip-egress"}
            assert service["read_only"]
            assert service["environment"].get("GEOIPUPDATE_ACCOUNT_ID")
            assert service["environment"].get("GEOIPUPDATE_LICENSE_KEY")
            assert service["environment"]["GEOIPUPDATE_FREQUENCY"] == "72"
            assert len(service["volumes"]) == 1
            volume = service["volumes"][0]
            assert volume["source"] == f"{prefix}-geoip"
            assert volume["target"] == "/usr/share/GeoIP"
            for app in (f"{prefix}-web", f"{prefix}-caddy"):
                mounts = [v for v in services[app]["volumes"] if v["target"] == "/usr/share/GeoIP"]
                assert len(mounts) == 1 and mounts[0]["read_only"]
        elif name.endswith("-clickhouse"):
            prefix = name.removesuffix("-clickhouse")
            assert not service.get("ports") and not service.get("networks")
            assert not service.get("cap_add")
            assert service["network_mode"] == f"service:{prefix}-web-net"
            assert service["depends_on"][f"{prefix}-web-net"]["condition"] == "service_healthy"
            assert service["environment"].get("CLICKHOUSE_PASSWORD"), "Missing analytics password"
            web = services[f"{prefix}-web"]
            assert web["environment"]["CLICKHOUSE_URL"] == "http://127.0.0.1:8123"
            assert web["environment"]["CLICKHOUSE_PASSWORD"] == service["environment"]["CLICKHOUSE_PASSWORD"]
            assert web["depends_on"][name]["condition"] == "service_healthy"
        else:
            assert not service.get("ports") and not service.get("networks")
            assert not service.get("cap_add")
            assert service["network_mode"] == f"service:{name}-net"
            assert service["depends_on"][f"{name}-net"]["condition"] == "service_healthy"
        if name.endswith("-web"):
            env = service["environment"]
            if env.get("TAILSCALE_GEOIP_OBSERVATIONS"):
                assert env["TAILSCALE_GEOIP_OBSERVATIONS"] == "/run/cpm-observations/tailscale-peers.json"
                observations = [v for v in service["volumes"] if v["target"] == "/run/cpm-observations"]
                assert len(observations) == 1 and observations[0]["read_only"]
                assert observations[0]["source"] == str(ROOT / "deployment/runtime")

            for key in ("SESSION_SECRET", "ADMIN_USERNAME", "ADMIN_PASSWORD"):
                assert env.get(key), f"Missing {key} for {name}"
            assert len(env["SESSION_SECRET"]) >= 32, f"Short session secret for {name}"
            assert env["AUTH_ALLOW_SELF_REGISTRATION"] == "false"
            secrets.append(env["SESSION_SECRET"])
    assert len(set(secrets)) == 2, "Use different session secrets for ICPM and PCPM"
    print("PASS: Compose ports, namespaces, privileges, health gates and required credentials")
    policy = ROOT / "deployment/generated/policy"
    for name in expected:
        rules = (policy / (name.removesuffix("-net") + ".nft")).read_text()
        rules = re.sub(r'include "/etc/cpm/policy/([^"/]+)"',
                       lambda m: (policy / m[1]).read_text(), rules)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".nft") as rendered:
            rendered.write(rules)
            rendered.flush()
            run("nft", "--check", "--file", rendered.name)
        print(f"PASS: nft syntax {name}")
    if "--live" in sys.argv:
        validate_live_namespaces(services)
        print("Live namespaces and ClickHouse connectivity verified; authenticated API behavior and tailnet ACLs are not checked here.")
    else:
        print("Static checks only; use --live after deployment to check namespace attachment and ClickHouse connectivity.")

if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        if error.cmd[0] == "nft":
            print(error.stderr)
        raise SystemExit(f"Validation command failed: {error.cmd[0]}") from None
