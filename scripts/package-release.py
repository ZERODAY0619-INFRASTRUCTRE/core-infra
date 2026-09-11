#!/usr/bin/env python3
import hashlib, io, json, pathlib, subprocess, tarfile
ROOT = pathlib.Path(__file__).resolve().parent.parent

def git(*args, cwd=ROOT):
    return subprocess.check_output(["git", *args], cwd=cwd)

subprocess.run(["python3", str(ROOT / "scripts/app-source.py"), "check"], check=True)
subprocess.run(["python3", str(ROOT / "scripts/scan-publish.py")], check=True)
assert not git("status", "--porcelain").strip(), "Commit infra changes before packaging"
app = ROOT / "apps/caddy-proxy-manager"
infra_rev = git("rev-parse", "HEAD").decode().strip()
app_rev = git("rev-parse", "HEAD", cwd=app).decode().strip()
app_version = json.loads((app / "package.json").read_text())["version"]
source_lock = json.loads((ROOT / "patches/caddy-proxy-manager/upstream.json").read_text())
out = ROOT / "artifacts" / ("infra-" + infra_rev[:12])
out.mkdir(parents=True, exist_ok=True)
# Bundles retain Git history; the tarball is an offline source export, without runtime data.
for name, repo in (("infra", ROOT),):
    target = out / (name + ".bundle")
    if target.exists(): target.unlink()
    subprocess.run(["git", "bundle", "create", str(target), "HEAD"], cwd=repo, check=True)
archive_path = out / "source.tar.gz"
with tarfile.open(archive_path, "w:gz") as target:
    for repo, prefix in ((ROOT, "infra/"),):
        blob = git("archive", "--format=tar", "--prefix=" + prefix, "HEAD", cwd=repo)
        with tarfile.open(fileobj=io.BytesIO(blob)) as source:
            for item in source:
                target.addfile(item, source.extractfile(item) if item.isfile() else None)
(out / "release.json").write_text(json.dumps({"infra_commit": infra_rev, "app_commit": app_rev, "app_version": app_version, "app_source": source_lock,
    "note": "Source/Git export only; upstream source is fetched by app-source.py; no images, dependencies, secrets, DB or deployment actions."}, indent=2) + "\n")
files = sorted(p for p in out.iterdir() if p.name != "SHA256SUMS")
(out / "SHA256SUMS").write_text("".join(hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.name + "\n" for p in files))
print(out)
