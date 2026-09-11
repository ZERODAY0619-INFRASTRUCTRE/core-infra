#!/usr/bin/env python3
"""Offline repository/Compose contract checks; no daemon calls or secret resolution."""
import json, subprocess, pathlib, re, os, tempfile
from site_config import settings, render, KEYS
ROOT = pathlib.Path(__file__).resolve().parent.parent

def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()

def compose():
    return json.loads(subprocess.check_output([
        "docker", "compose", "--env-file", str(ROOT / ".env.example"), "-f", str(ROOT / "compose.yaml"),
        "--profile", "*", "config", "--no-env-resolution", "--format", "json"
    ], cwd=ROOT, text=True, env={k:v for k,v in os.environ.items() if k not in {line.split("=", 1)[0] for line in (ROOT / ".env.example").read_text().splitlines() if "=" in line and not line.startswith("#")}}))

def contract(config):
    keys = ("network_mode", "networks", "ports", "cap_add", "cap_drop", "security_opt",
            "read_only", "restart", "depends_on", "sysctls", "devices", "healthcheck", "profiles")
    result = {name: {**{k: value[k] for k in keys if k in value},
                   "volumes": [{k: v[k] for k in ("type", "target", "read_only") if k in v}
                               | ({"source": v["source"]} if v["type"] == "volume" else {})
                               for v in value.get("volumes", [])]}
            for name, value in config["services"].items()}
    for service in result.values():
        health = service.get("healthcheck", {})
        if "test" in health:
            health["test"] = [v.rstrip() for v in health["test"]]
    return result

def main():
    site = settings(ROOT / ".env.example", environ={})
    c = compose()
    assert contract(c) == json.loads((ROOT / "config/common/deployment-contract.json").read_text()), "Deployment network/volume contract changed"
    app = ROOT / "apps/caddy-proxy-manager"
    subprocess.run(["python3", str(ROOT / "scripts/app-source.py"), "check"], check=True)
    assert not git("ls-files", "apps/caddy-proxy-manager"), "Generated app source must not be tracked"
    s = c["services"]
    for kind in ("web", "caddy"):
        internal, public = s["icpm-" + kind], s["pcpm-" + kind]
        assert internal["image"] == public["image"], "Instances must use one image"
        assert internal["build"] == public["build"], "Instances must use one build"
        assert pathlib.Path(internal["build"]["context"]) == app
    envs = {instance: s[instance + "-web"]["environment"] for instance in ("icpm", "pcpm")}
    assert all(not service.get("env_file") for service in s.values()), "Use only the root .env"
    assert not envs["icpm"].get("ANUBIS_PROTECTED_DOMAIN")
    assert envs["pcpm"]["ANUBIS_PROTECTED_DOMAIN"] == site["ANUBIS_PROTECTED_DOMAIN"]
    for service in s.values():
        for volume in service.get("volumes", []):
            if volume["type"] != "bind": continue
            p = pathlib.Path(volume["source"])
            if p == ROOT / "deployment/runtime": continue
            if p.is_relative_to(ROOT / "deployment/generated"):
                relative = p.relative_to(ROOT / "deployment/generated")
                template = ROOT / "config/templates" / relative
                assert template.is_dir() or template.with_name(template.name + ".tmpl").is_file(), "Missing template"
                continue
            assert p.exists(), "Missing bind source: " + str(p)
    for f in git("ls-files").splitlines():
        p = pathlib.PurePosixPath(f)
        assert not any(x in p.parts for x in ("node_modules", "backups", "runtime", "generated", ".next")), f
        assert not f.endswith((".db", ".key", ".pem", ".log")), f
        assert not (f.startswith("deployment/secrets/") and not f.endswith(".example")), f
        assert not (p.name.startswith(".env") and p.name != ".env.example"), f
    with tempfile.TemporaryDirectory() as output:
        render(site, pathlib.Path(output))
    print("PASS: pinned upstream + custom patch, both instance profiles, original network/volume contracts, bind paths and tracked file exclusions")

if __name__ == "__main__": main()
