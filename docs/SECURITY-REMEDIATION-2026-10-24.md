# Security remediation, 2026-10-24

## Scope and result

This record covers the Debian host and the CPM, Matrix, and CV containers inspected on 2026-10-24. Passwordless sudo is intentional and excluded at the operator's request. The image scans use Trivy 0.76.1 and its 2026-10-24 vulnerability database. A complete source-level repository audit was unavailable because the Codex Security standard-scan tool was not installed in this environment.

| Component | Deployed remediation | High or critical image findings after deployment |
| --- | --- | ---: |
| GeoIPUpdate (two containers) | Brotli 1.2.1, Alpine package updates, Go 1.27.3 and x/net 0.60.0 rebuild | 0 |
| Discord bridge | Brotli 1.2.1, Go 1.27.3 and x/net 0.60.0 rebuild, static libolm 3.2.16 | 0 |
| Caddy (three containers) | Go 1.27.3, Coraza 3.8.1, x/net 0.60.0, Debian package updates | 0 |
| Netguard (five containers) | Updated Alpine packages | 0 |
| ClickHouse (two containers) | Preserved ClickHouse 26.8.2.7, updated Alpine packages | 0 |
| Matrix PostgreSQL | PostgreSQL 17.11 on Alpine 3.24, nonroot user | 0 |
| CV site | Updated Alpine packages, removed unused runtime pip | 0 |
| CPM web | Bun 1.4.4, updated application dependencies, Debian package updates | 43 high, no critical; Debian packages with no fixed version in the scanner database |
| Anubis | Official 1.28.2 binary, Bun 1.4.4, Debian package updates, nonroot runtime | 44 high, no critical; 43 Debian records without a fixed version and one x/net 0.59 record |
| Synapse | Synapse 1.163.2, Debian package updates, patched Debian Brotli, nonroot runtime | 63 high, one critical in the scanner report; 57 Debian records, including a stale Brotli base-layer record, and seven Python records |
| Tailscale | Official stable 1.104.2 built with Go 1.27.3 | Three high records for x/net 0.59 in three binaries |

The reported Synapse Python records include urllib3, msgpack, and setuptools versions retained in older image layers. The live container has urllib3 2.8.0, msgpack 1.2.1, and setuptools 83.0.0. Three Twisted 26.4.0 records remain; the scanner lists only 26.10.0rc1 as fixed, so no stable upgrade was deployed. The live Synapse Brotli package is Debian `libbrotli1` 1.1.0-2+deb13u1. The user-reported GHSA-9v8h-qqgm-4m35 affects upstream Brotli before 1.2.1; Debian packages must be judged against Debian's backport status rather than upstream numbering alone.

The Anubis and Tailscale x/net findings concern HTTP/2 SETTINGS handling. No stable vendor image containing x/net 0.60.0 was available during this remediation. Anubis serves its backend on loopback behind Caddy, which limits direct exposure; Tailscale remains restricted to its tailnet network path. These are mitigations, not a finding closure. Rebuild or upgrade these images when the vendors publish fixed binaries. Keep tracking Debian fixes for the remaining operating-system findings and a stable Twisted release.

The CPM web production dependency audit retains one high node-forge advisory without a published fixed version. Source inspection found node-forge used for certificate generation and signing, outside the reported signature-verification path. Reassess when a fixed release or code-path change becomes available.

## Rebuild and deployment

From the CPM infrastructure repository root:

```sh
./scripts/build.sh all
./deployment/brotli/build-brotli-images.sh
docker build --network host -f deployment/netguard/Dockerfile -t cpm-netguard:security-20261024 deployment/netguard
docker build --network host -f deployment/brotli/clickhouse-secure.Dockerfile -t cpm-clickhouse:26.8.2.7-security-20261024 deployment/brotli
```

Set the `CPM_WEB_IMAGE`, `CPM_CADDY_IMAGE`, and `CPM_ANUBIS_IMAGE` values printed by `scripts/build.sh` in the local `.env` before recreating CPM services. Preserve the Compose image references for GeoIPUpdate, Netguard, and ClickHouse. The Matrix image build commands are in `/opt/debian.kr/mautrix-discord/security/README.md`; its bridge image comes from `build-brotli-images.sh`. The CV image is built from `/home/debian/cv.zeroday0619.dev/Dockerfile` and deployed with `compose.cpm.yaml` under project `cv`.

Before upgrading Synapse or PostgreSQL, back up the Matrix database and confirm the restore procedure. The pre-upgrade SQL backup is `/opt/debian.kr/mautrix-discord/backups/postgres-pre-security-upgrade-20261024.sql`, owned by root with mode 0600. The PostgreSQL data migration was exercised against a consistent `pg_basebackup` copy before the live rollout.

## Validation

- `scripts/validate.sh` passed.
- `python3 deployment/validate.py --live` passed the network policy, namespace, and ClickHouse checks.
- CPM web type checking and 1,244 tests passed. The production web image built successfully.
- The Caddy rebuild retained the original 203 modules and its three containers were healthy.
- Anubis health check, Matrix client versions endpoint, bridge startup, PostgreSQL queries, Tailscale peer connection, and the CV HTTP response succeeded.
- All containers with configured health checks were healthy after the rollout. Browser login journeys and tailnet ACL behavior were not exercised.

Human review and environment-specific acceptance testing remain required before treating these AI-assisted changes as complete for production policy purposes. No commit or pull request was created.
