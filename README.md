# ICPM / PCPM Infrastructure

이 저장소 하나에 배포 설정과 Caddy Proxy Manager 커스텀 패치를 관리한다.
앱 원본은 공개 저장소의 **Ingressi v2.10.0 커밋**에 고정하고, 빌드 전에 패치를 적용한다.
별도 앱 fork나 submodule은 필요 없다. 실제 환경설정은 루트 `.env` 하나다.

```sh
git clone git@github.com:ZERODAY0619-INFRASTRUCTRE/core-infra.git
cd core-infra
python3 scripts/app-source.py prepare
./scripts/validate.sh
umask 077
cp -n .env.example .env
# .env에 실제 환경값 입력
./scripts/build.sh
```

- `patches/caddy-proxy-manager/upstream.json`: 공식 원본 커밋, 패치 SHA-256, 적용 후 소스 트리
- `patches/caddy-proxy-manager/000N-*.patch`: 기능별 커스텀 변경 (메일 형식)
- `patches/caddy-proxy-manager/series`: 적용 순서; `0000-cover-letter.patch`는 전체 설명
- `apps/caddy-proxy-manager/`: 자동 준비된 앱 소스, Git 제외
- `.env.example`: 모든 서비스 환경설정 예제
- `config/templates/`: 환경값으로 생성할 방화벽·Caddy·Anubis 정책
- `deployment/`, `scripts/`: 배포 및 검증 도구

두 인스턴스는 같은 앱 소스와 이미지를 사용한다. 기본 프로젝트 이름은 `cpm-preview`이며,
운영 전환 전 [이전 안내](docs/MIGRATION.ko.md)를 따른다. 같은 호스트에서 고정 네트워크와
공개 포트가 겹치는 구성을 병렬 실행하지 않는다.

[Anubis 콘솔 설정](docs/ANUBIS.ko.md) · [환경설정](docs/ENV.ko.md) · [패치 업데이트](docs/UPDATE.ko.md) · [Git 업로드](docs/GIT.ko.md)

실제 `.env`, DB, 키, 로그, 생성 소스와 백업은 업로드하지 않는다.
기존 운영 디렉터리와 과거 앱 저장소는 이전·복구용으로 보존하며 새 업로드 대상은 이 저장소다.

## 2026-10 보안 이미지

`scripts/build.sh`는 보안 의존성 갱신이 포함된 앱 패치 시리즈를 검증한 뒤
웹 이미지를 빌드한다. 별도 보안 패치를 다시 적용하지 않는다. Bun 1.4.4와 갱신된 잠금 파일을 사용한다.
Caddy는 Go 1.27.3, Coraza 3.8.1 및 x/net 0.60.0으로 다시 빌드한다. Anubis는 공식 1.28.2 실행 파일과 Bun 1.4.4를 사용하고 Debian 패키지를 갱신한다. 의존성 변경은 원본 앱 패치 시리즈에 포함된다.

`deployment/brotli/build-brotli-images.sh`는 공식 Alpine APK의 SHA-256을 검사한 뒤,
GeoIPUpdate와 Discord 브리지의 Brotli 1.2.1 이미지를 빌드하고 Alpine 패키지를 갱신한다. ClickHouse는 `deployment/brotli/clickhouse-secure.Dockerfile`로 기존 서버 버전을 유지하며 빌드한다.
`deployment/brotli/build-bun-images.sh`는 이 호스트의 기존 웹·Anubis 이미지 ID를
검사한 뒤 Bun만 교체하는 긴급 복구용 빌드다. 새 앱 빌드에는 `scripts/build.sh`를 사용한다.

Compose의 웹 서비스에는 자동 빌드 설정이 없다. 배포 전 보안 이미지를 빌드하고,
`.env`의 이미지 태그를 확인한다. 이미지가 없으면 배포를 중단한다.

## GitHub Actions 검증

Push, Pull Request 및 Actions의 수동 실행에서 다음 검사를 수행한다.

1. 고정한 원본에 패치 적용, 해시·소스 트리 검증, Compose 계약 검사
2. 배포 도구·패치 관리 테스트와 업로드 파일 및 Git 이력의 크레덴셜 패턴 검사
3. Node 24 / Bun 1.4.4에서 패치 시리즈에 포함된 잠금 파일로 앱 테스트, 커스텀 테스트, TypeScript 검사
4. web(Next.js 프로덕션 빌드 포함), Caddy, Anubis, netguard Docker 이미지 빌드 및 실행 파일 검사
5. 격리된 실제 Anubis에서 세부 설정 적용·거부·재시작 후 유지 검사

앞 단계가 통과해야 다음 단계가 실행되며, 이미지 빌드는 컴포넌트별로 병렬 실행한다.
실제 `.env`나 GitHub Secrets 없이 공개 원본과 `.env.example`을 사용한다.
이미지 게시·운영 배포는 수행하지 않으며, 브라우저 E2E나 운영 서비스 연결은 검증 범위에 포함하지 않는다.

## Ingressi 2.10.0 및 Origin CA

원본은 `ingres-si/ingressi`의 `f9b7e42fc82f0f5a20c9d6d8d212327c7b981380`에 고정한다.
패치 9개는 기존 인증·Anubis 기능과 Fluent 2 파스텔 인터페이스를 포함한다.
재구성된 앱 트리는 `106ae542b6566edcbfb3060d2455b54d6f828f84`다.

두 웹 서비스는 공개 Cloudflare Origin CA ECC 루트 인증서를 읽기 전용으로 마운트한다.
`NODE_EXTRA_CA_CERTS`는 인증서 검증을 유지하면서 해당 CA를 신뢰하게 한다.
서버 인증서와 개인키는 저장소에 포함하지 않는다. Cloudflare의 Full (strict) 설정과
운영 서버의 Origin 인증서는 별도로 유지한다.
