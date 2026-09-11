# CPM 콘솔의 Anubis 설정

Settings → Security → Anubis에서 전역 보호와 세부 설정을 관리한다.
Proxy Hosts 목록에는 각 호스트의 Anubis 토글이 있으며 모바일 카드에서도 사용할 수 있다.

## 적용 규칙

- 전역 OFF는 해당 CPM 인스턴스의 Anubis 보호를 모두 중지한다. 호스트별 선택은 보존된다.
- 전역 ON일 때 호스트별 OFF는 해당 호스트의 도메인 별칭들을 보호 대상에서 제외한다.
- 기존 호스트와 새 호스트는 기본 ON이다. 호스트 자체가 중지돼 있으면 보호 선택은 보존하되 적용 상태는 일시중지로 표시한다.
- 현재 PCPM의 `ANUBIS_PROTECTED_DOMAIN` 바로 아래 한 단계 서브도메인에 적용된다. 범위 밖 도메인이나 Anubis가 없는 ICPM은 적용 불가로 표시한다.
- 개별 도메인은 와일드카드 호스트보다 우선한다. 동일 도메인을 여러 호스트가 사용하면 하나라도 ON인 경우 보호한다.
- 보호 도메인에 속한 미등록 호스트는 기존 기본 보호를 유지한다.

호스트 선택은 기존 `proxy_hosts.meta.anubis_enabled`에 저장하고 일반 호스트 편집 시에도 보존한다.
전역·세부 설정은 기존 settings 테이블의 `anubis` 키에 저장한다. DB 스키마 변경은 없다.

## 세부 설정

| 항목 | 범위 | 기본값 |
| --- | --- | --- |
| 챌린지 방식 | fast / slow / metarefresh | fast |
| 난이도 | 1–8 정수; metarefresh에서는 대기 초 | 4 |
| 인증 쿠키 유효기간 | 1–168시간 | 24시간 |
| 안내 언어 | 브라우저 자동 / 영어 / 한국어 / 일본어 / 독일어 / 프랑스어 / 스페인어 | 자동 |
| 간단한 설명 | ON/OFF | OFF |
| 크롤링 거부 robots.txt | ON/OFF | OFF |

난이도를 높이면 클라이언트의 계산량이 크게 증가한다. 쿠키 유효기간 변경은 새로 발급되는 쿠키에 적용되며 기존 쿠키의 만료 시각을 소급 변경하지 않는다.
robots.txt는 크롤러에 대한 요청이며 접근 제어를 대신하지 않는다.

관리자 권한과 기존 세션 CSRF 검사를 통과한 요청만 설정을 바꿀 수 있다.
`PUT /api/v1/anubis`는 `{ "enabled": true }`, `{ "hostId": 1, "enabled": false }`,
또는 `{ "options": { ...전체 세부 설정... } }`를 받는다.
`GET /api/v1/anubis`에서 기본값이 반영된 설정과 지원 여부를 조회한다.

## 실행 방식

`cpm-anubis` 이미지는 고정된 Anubis v1.27.0 바이너리와 비권한 Bun 실행기를 포함한다.
CPM과 실행기는 `pcpm-anubis-control` named volume에 검증된 JSON 설정과 적용 상태만 공유한다.
Docker 소켓·호스트 프로세스 제어 권한을 앱에 전달하지 않는다.
실행기는 허용된 항목만 Anubis 정책·환경변수로 변환하며 고정된 실행 파일만 실행한다.
기존 Authentik OIDC 프로토콜 예외, 서명 키, 보안 쿠키 속성, 네트워크 바인딩은 세부 설정에서 바꾸지 않는다.

전역·호스트 토글은 Caddy 설정을 갱신한다. 세부 설정 변경은 Anubis 자식 프로세스만 잠시 재시작한다.
CPM은 실행기가 새 설정으로 정상 기동했다고 확인한 후에만 성공을 표시한다.
적용 실패 시 이전 DB 설정과 Caddy·Anubis 설정을 복구하고, 복구 확인에 실패한 경우 이를 오류로 알린다.
실행기는 마지막 정상 세부 설정을 공유 볼륨에 보존한다.

## 배포

```sh
python3 scripts/app-source.py prepare
./scripts/build.sh
```

빌드 출력에 맞춰 루트 `.env`의 `CPM_WEB_IMAGE`, `CPM_CADDY_IMAGE`, `CPM_ANUBIS_IMAGE`를 설정한다.
기존 `ANUBIS_PRIVATE_KEY_HEX`는 그대로 유지한다. 기존 배포에서 최초 반영 전 DB와 설정을 백업한다.

```sh
./scripts/compose.sh up -d --no-build --pull never --wait
python3 deployment/validate.py --live
```

새 `pcpm-anubis-control` 볼륨은 Anubis 이미지의 UID/GID 10001 디렉터리 권한으로 초기화된다.
Anubis 서비스가 먼저 기동되어 볼륨을 초기화한 후 web의 설정 적용이 시작된다.
기존 Anubis 정책 bind mount는 JSON 템플릿으로 변경되며 기존 정책 의미는 유지된다.

CI는 앱·API·UI 테스트, 네 컴포넌트 이미지 빌드와 실제 Anubis의 설정 변경·재시작 검사를 수행한다.
런타임 검사는 공개 포트나 운영 볼륨 없이 격리 컨테이너에서 실행한다.

참고: [Anubis v1.27.0 실행 옵션](https://github.com/TecharoHQ/anubis/blob/v1.27.0/cmd/anubis/main.go),
[Anubis v1.27.0 정책](https://github.com/TecharoHQ/anubis/blob/v1.27.0/docs/docs/admin/policies.mdx).
