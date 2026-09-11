# 로컬 환경설정과 공개 범위

모든 서비스 설정은 배포 저장소 루트의 `.env` 하나에 입력한다.
Git에는 `.env.example`만 올린다. 자동 준비되는 앱 소스에 별도의 `.env`를 만들 필요가 없다.
Compose가 서비스별 변수만 전달하므로 내부·외부 앱의 자격증명은 서로 섞이지 않는다.

```sh
# 새 설치에서만 실행: 기존 .env를 덮어쓰지 않는다.
umask 077
cp -n .env.example .env
chmod 600 .env
# 편집기로 주소와 비밀값 입력 후:
python3 scripts/render-config.py
./scripts/validate.sh
./scripts/compose.sh config --quiet
```

`ICPM_SESSION_SECRET`, `ICPM_ADMIN_PASSWORD`, `ICPM_OAUTH_CLIENT_*`는 내부 앱,
`PCPM_SESSION_SECRET`, `PCPM_ADMIN_PASSWORD`, `PCPM_OAUTH_CLIENT_*`는 외부 앱에만 전달된다.
두 SESSION_SECRET은 서로 다른 32자 이상 값을 사용한다. 기존 배포 이전 시 기존 값을 보존한다.
Tailscale은 `TS_AUTHKEY`, Anubis는 `ANUBIS_PRIVATE_KEY_HEX`에 입력한다.
GeoIP는 `ICPM_GEOIPUPDATE_*`, `PCPM_GEOIPUPDATE_*`를 사용한다.
`CLICKHOUSE_PASSWORD`는 두 ClickHouse와 각 웹에서 공유한다.

| 설정 | 용도 |
| --- | --- |
| `PUBLIC_BIND_IP` | 공개 80/443 바인딩, 내부 웹의 SSO 접근 경로, 방화벽 우회 차단 대상 |
| `HOST_TAILNET_IP` | 호스트 자체로의 프록시 우회를 차단할 Tailnet IPv4 |
| `SSO_HOST` | OAuth issuer, 이름 해석, Anubis의 정확한 SSO 프로토콜 호스트 예외 |
| `ANUBIS_PROTECTED_DOMAIN` | 외부 보호 도메인과 리다이렉트 범위 |
| `AUTHENTIK_UPSTREAM_IP`, `AUTHENTIK_UPSTREAM_PORT` | Authentik outpost의 HTTPS backend |
| `AUTHENTIK_TLS_INSECURE` | 기본값 `false`; 기존 자체 서명 backend를 유지할 때만 명시적으로 `true` |
| `ICPM_BASE_URL`, `PCPM_BASE_URL` | 두 관리 UI의 URL |
| `CLICKHOUSE_PASSWORD` | 웹과 ClickHouse가 공유하는 비밀번호 |

주소·호스트·포트 설정은 리터럴만 허용한다. 소문자 DNS 호스트와 IPv4를 쓰며,
주석을 같은 줄에 붙이거나 `${VAR}` 확장을 쓰지 않는다. 셸 환경변수는 `.env`보다 우선한다.
SSO 호스트는 보호 도메인 아래에 두고 Authentik의 provider slug는 `icpm`, `pcpm`으로 맞춘다.
`.env.example`의 문서용 주소는 운영에서 사용할 수 없으므로 반드시 바꾼다.
Docker 내부의 두 고정 네트워크와 포트는 배포 구조의 일부이며 서버 비밀값이 아니다.

Compose는 마운트 파일의 내용을 치환하지 않는다. `scripts/render-config.py`가
`config/templates/`를 검증된 환경값으로 렌더링하여 `deployment/generated/`에 기록한다.
생성물은 직접 편집하지 않는다. `scripts/compose.sh`는 생성 후 같은 `.env`로 Compose를 실행한다.
설정 변경 시 영향을 받는 컨테이너를 재생성해야 변경된 bind mount가 적용된다.
관측기의 `deployment/runtime/` 디렉터리도 이전 문서에 따라 준비한다.

`config`를 값 출력 옵션으로 실행하면 비밀번호가 표시될 수 있다. 공유할 검증 결과에는
`config --quiet`와 `scripts/validate.sh`를 사용한다. 비밀값을 빌드 인자나 Dockerfile에 넣지 않는다.

## 공개 전 검사

```sh
python3 scripts/scan-publish.py
# 추가로 기존 비밀 파일의 실제 값과 대조할 때 (값은 출력하지 않음):
python3 scripts/scan-publish.py --private-env /secure/path/old.env
```

검사는 현재 추적 파일과 두 저장소의 모든 로컬 ref에서 도달 가능한 Git 객체를 대상으로 한다.
로컬 `.env`의 서버별 값, 비밀 환경값, 일부 토큰 형식과 PEM 개인키를 확인한다.
CI에서는 로컬 비밀 파일이 없으므로 알려진 실제 값과의 대조 범위가 줄어든다.
원본의 공개 AWS 예제 ID와 확인된 Cypress 테스트 키의 정확한 Git blob만 예외 처리한다.
정규식 검사는 모든 비밀을 찾아낸다는 보장이 없으므로 새 설정을 추가할 때 공개 여부도 검토한다.
릴리스 생성 스크립트도 이 검사를 통과해야 bundle/archive를 만든다.

업로드 대상은 `git-ready/publish/infra` 하나다. 앱은 공개 원본과 패치로 재현하므로
별도 앱 저장소를 올릴 필요가 없다. `apps/`, 실제 `.env`, 이전 작업 저장소와 백업은
업로드 대상에 포함하지 않는다. 과거 백업과 기존 운영 디렉터리는 별도로 보존한다.
