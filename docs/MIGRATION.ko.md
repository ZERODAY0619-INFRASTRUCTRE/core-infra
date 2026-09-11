# 기존 운영에서 새 구조로 이전

이 문서는 기존 배포에서 패치 기반 저장소로 운영을 전환하는 절차다.
전환 후에는 새 저장소의 `scripts/compose.sh`로 관리한다. 기존 소스·설정은 복구용으로 보존한다.
서버별 전환 기록과 비밀값을 포함하는 백업은 Git에서 제외된 `deployment/backups/`에 보관한다.

## 변경과 검증 범위

PCPM의 원본 f1257934를 기준으로 통합한 뒤 최신 정식 릴리스 v1.11.2 (7e579175)로 갱신했다. ICPM 기준 f6ff473a 이후 원본 커밋 7개가
포함되어 ICPM 의존성/Caddy pin도 갱신된다. PCPM의 Authentik 포트/TLS 및 입력 검증 수정은
공통 기능으로 적용한다. Anubis는 PCPM에서만 켜진다. 네트워크 namespace, 방화벽,
공개 포트, 서비스 의존성, 볼륨 이름과 마운트 대상은 기존 계약을 유지한다.

## 설정 준비

먼저 `python3 scripts/app-source.py prepare`로 원본과 패치를 적용한다. 앱 submodule은 사용하지 않는다.

1. 루트 `.env.example`을 `.env`로 복사하고 [환경설정](ENV.ko.md)을 따른다.
   현재 준비본의 `.env`에는 기존 서버 주소만 보존되어 있고 자격증명은 비어 있다.
2. 기존 내부 앱 `.env` 다음 기존 `deployment/secrets/icpm.env` 순서의 최종 값을 읽어
   `SESSION_SECRET` → `ICPM_SESSION_SECRET`, `ADMIN_USERNAME` → `ICPM_ADMIN_USERNAME`,
   `ADMIN_PASSWORD` → `ICPM_ADMIN_PASSWORD`, `OAUTH_CLIENT_ID` → `ICPM_OAUTH_CLIENT_ID`,
   `OAUTH_CLIENT_SECRET` → `ICPM_OAUTH_CLIENT_SECRET`으로 루트 `.env`에 입력한다.
   PCPM도 같은 순서로 최종 값을 읽고 `PCPM_` 접두사를 붙인다.
3. 기존 Tailscale 키는 `TS_AUTHKEY`, Anubis의 `ED25519_PRIVATE_KEY_HEX`는
   `ANUBIS_PRIVATE_KEY_HEX`로 입력한다. GeoIP 계정/키에는 `ICPM_` 또는 `PCPM_` 접두사를 붙인다.
4. 기존 루트의 프로파일, ClickHouse 비밀번호, BASE_URL과 SESSION_SECRET을 보존한다.
   새 배포에서는 서비스별 env 파일을 읽지 않는다. 모든 설정을 루트 `.env` 하나에 모으고 권한을 0600으로 한다.
5. `deployment/runtime` 디렉터리를 만들고 기존 관측기 사용자의 쓰기 권한을 보존한다.
   systemd service의 `/opt/infra`는 최종 설치 경로에 맞춰 변경한다.

Compose의 `environment`는 `.env`의 접두사 변수를 각 서비스가 기대하는 원래 이름으로 전달한다.
서버별 값과 비밀값은 `.env`에서만 바꾸고, 고정 내부 연결과 서비스 분리는 Compose로 관리한다.
`python3 scripts/render-config.py`가 방화벽·Caddy·Anubis 템플릿에 같은 환경값을 적용한다.
Compose 실행은 `./scripts/compose.sh`를 사용한다.

## 전환 시점

- 공통 web·Caddy 및 Anubis 실행기 이미지를 빌드하고 `CPM_WEB_IMAGE`, `CPM_CADDY_IMAGE`, `CPM_ANUBIS_IMAGE`에 빌드 태그를 설정한다.
- 운영 DB·볼륨과 기존 환경설정 백업을 준비하고 기존 이미지 ID/태그를 기록한다.
- 기존 Compose 프로젝트 이름 `cpm`과 볼륨이 맞는지 확인한다. 새 `.env`에
  `COMPOSE_PROJECT_NAME=cpm`을 설정해야 기존 `cpm_*` 볼륨을 사용한다.
- 기존 서비스 관리 방식과 systemd 타이머를 함께 전환한다. 같은 서버에서 두 구성을 동시에 올리지 않는다.
- 새 설치 경로에서 `python3 deployment/validate.py`로 실제 비밀값/방화벽 계약을 검사한다.
  이후 계획한 점검 시간에 서비스를 전환하고 네임스페이스 의존 서비스도 함께 재생성한다.
- 두 관리 UI 로그인, OAuth 역할 동기화, Authentik 보호 경로, 외부 Anubis, 인증서,
  오류 피드백, Metrics, ClickHouse를 확인한다. 관측기 systemd 경로도 확인한다.

문제가 생기면 새 구성을 중지하고 기존 Compose/이미지/설정으로 복귀한다. DB 스키마가 바뀌었다면
이전 DB 백업 복원 여부를 먼저 판단한다. `docker compose down -v`는 사용하지 않는다.

`./scripts/validate.sh`는 비밀값 없이 구조만 검증한다. 운영 로그인/실제 배포 검증을 대신하지 않는다.

## v1.11.2 배포 점검

기존 공통 앱 이후 변경은 gRPC v1.83.1 → v1.83.2와 로그 권한 관련 주석/진단 안내다.
이 구간에 추가된 DB 마이그레이션은 없다. TOMORI 및 인스턴스 분리 설정은 유지한다.
현재 두 Caddy의 `/logs`는 named volume이다. 추후 bind mount로 변경하면 Caddy UID/GID에
디렉터리 읽기·쓰기·실행 권한을 줘야 로그 압축·삭제가 동작한다.
`waf-audit.log`는 web의 보조 그룹(GID 10000)이 쓸 수 있어야 읽은 로그를 비울 수 있다.
운영 파일 권한은 이번 소스 갱신에서 변경하지 않는다.

## 전환 후 운영 확인

```sh
./scripts/compose.sh ps
python3 deployment/validate.py --live
systemctl status cpm-tailnet-observer.timer
```

`--live`는 Authentik relay를 포함한 서비스 계약, 실제 네트워크 namespace 연결과
두 web의 ClickHouse 연결을 검사한다. 추가로 두 관리 UI 로그인과 인증된 API 조회,
OAuth 제공자 discovery, 기존 DB 무결성·주요 데이터 개수·프록시 호스트 보존을 확인한다.
OAuth discovery 성공만으로 실제 사용자의 SSO 로그인·역할 동기화까지 검증되지는 않는다.

서비스 중지 후 모든 named volume을 백업하고 체크섬을 기록해야 한다. 복구용 Compose에는
프로파일 서비스를 포함하고 이미지 ID를 고정한다. 기존 DB 복원은 전환 이후 데이터를
되돌리므로, 장애 원인과 스키마 호환성을 확인한 후 별도로 판단한다.

관측기 systemd unit의 `ExecStart`와 `ReadWritePaths`를 새 저장소의 절대 경로로 바꾸고
`systemctl daemon-reload` 후 service와 timer를 시작한다. 전환 완료 후 모든 컨테이너의
Compose 작업 경로와 bind mount가 새 저장소를 가리키는지 확인한다.
