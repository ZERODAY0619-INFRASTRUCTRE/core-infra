# 기존 운영에서 새 구조로 이전

이 디렉터리는 별도 준비본이다. 기존 `/opt/infra/compose.yaml`, 두 앱 소스, 실행 중인 컨테이너,
볼륨, DB, 비밀값, 기존 패치는 수정하지 않았다. 이 문서는 운영 전환 절차이며 자동 실행하지 않는다.

## 변경과 검증 범위

PCPM의 원본 f1257934를 기준으로 통합한 뒤 최신 정식 릴리스 v1.11.2 (7e579175)로 갱신했다. ICPM 기준 f6ff473a 이후 원본 커밋 7개가
포함되어 ICPM 의존성/Caddy pin도 갱신된다. PCPM의 Authentik 포트/TLS 및 입력 검증 수정은
공통 기능으로 적용한다. Anubis는 PCPM에서만 켜진다. 네트워크 namespace, 방화벽,
공개 포트, 서비스 의존성, 볼륨 이름과 마운트 대상은 기존 계약을 유지한다.

## 설정 준비

1. `.env.example`을 `.env`로 복사하고 [환경설정](ENV.ko.md)에 따라 도메인/IP와 실제 값을 준비한다.
   현재 준비본의 `.env`에는 기존 서버의 주소만 보존되어 있다. 비밀번호는 별도로 옮겨야 한다.
2. `deployment/secrets/*.env.example`을 해당 `.env`로 복사한다. 파일 권한은 0600으로 한다.
3. 기존 내부 앱 `.env` 다음 기존 `deployment/secrets/icpm.env` 순서의 최종 환경변수를
   새 `deployment/secrets/icpm.env`에 옮긴다. PCPM도 같은 순서로 옮긴다.
   중복 키는 기존처럼 뒤 파일이 우선한다. 단순 연결로 중복 값을 방치하지 않는다.
4. Tailscale, Anubis, GeoIP 비밀 파일과 필요한 trust 파일을 안전한 별도 경로로 옮긴다.
   실제 비밀값은 이 작업 준비본에 복사하지 않았다. 기존 root `.env`의 프로파일과
   ClickHouse 비밀번호, BASE_URL도 보존한다. SESSION_SECRET을 새로 생성하면 기존 세션이 무효화된다.
5. `deployment/runtime` 디렉터리를 만들고 기존 관측기 사용자의 쓰기 권한을 보존한다.
   systemd service의 `/opt/infra`는 최종 설치 경로에 맞춰 변경한다. 현재 준비본에서 실행하지 않는다.

Compose의 `environment`는 env_file보다 우선한다. 인스턴스 식별 설정은 `config/*/web.env`,
BASE_URL·공통 런타임 설정과 ICPM의 Anubis 비활성화는 compose.yaml에 명시한다.
SSO/Anubis 도메인과 backend 주소는 루트 `.env`에서 설정한다.
`python3 scripts/render-config.py`가 방화벽·Caddy·Anubis 템플릿에 같은 값을 적용한다.
Compose 실행은 `./scripts/compose.sh`를 사용한다.

## 전환 시점

- 두 공통 이미지를 빌드하고 `CPM_WEB_IMAGE`, `CPM_CADDY_IMAGE`에 커밋 태그를 설정한다.
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
