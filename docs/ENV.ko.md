# 로컬 환경설정과 공개 범위

루트 `.env`는 서버 주소, Compose 설정, ClickHouse 비밀번호를 보관한다.
`deployment/secrets/*.env`는 서비스별 자격증명을 보관한다. 두 종류 모두 Git에서 제외된다.
`config/*/web.env`에는 공개 가능한 인스턴스 이름과 고정 컨테이너 내부 연결만 남긴다.
DB, 인증서, 키, 로그, 관측 결과, 생성된 정책, 릴리스 묶음도 추적하지 않는다.

```sh
# 새 설치에서만 실행: 기존 .env를 덮어쓰지 않는다.
umask 077
cp -n .env.example .env
for example in deployment/secrets/*.env.example; do
  cp -n "$example" "${example%.example}"
done
chmod 600 .env deployment/secrets/*.env
# 편집기로 실제 값 입력 후:
python3 scripts/render-config.py
./scripts/validate.sh
./scripts/compose.sh config --quiet
```

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
관측기의 `deployment/runtime/` 디렉터리와 서비스별 비밀 파일도 이전 문서에 따라 준비한다.

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

환경 분리된 업로드용 저장소는 `git-ready/publish/infra`와
`git-ready/publish/caddy-proxy-manager` 두 개다. 배포 저장소는 깨끗한 최초 커밋으로
새로 만들었고 앱은 upstream 이력을 유지한다. 기존 `git-ready/infra`와 그 산출물,
과거 패치 및 비공개 백업에는 서버 설정이 남아 있으므로 업로드하지 않는다.
이전 저장소의 이력·reflog·산출물은 삭제하거나 재작성하지 않았다.
이미 외부로 유출된 키가 있다면 이력 정리와 별개로 해당 키를 교체해야 한다.
