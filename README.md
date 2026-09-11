# ICPM / PCPM Infrastructure

이 저장소 하나에 배포 설정과 Caddy Proxy Manager 커스텀 패치를 관리한다.
앱 원본은 공개 저장소의 **v1.11.2 커밋**에 고정하고, 빌드 전에 패치를 적용한다.
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

[환경설정](docs/ENV.ko.md) · [패치 업데이트](docs/UPDATE.ko.md) · [Git 업로드](docs/GIT.ko.md)

실제 `.env`, DB, 키, 로그, 생성 소스와 백업은 업로드하지 않는다.
기존 운영 디렉터리와 과거 앱 저장소는 이전·복구용으로 보존하며 새 업로드 대상은 이 저장소다.
