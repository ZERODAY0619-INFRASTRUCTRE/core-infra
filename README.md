# ICPM / PCPM Infrastructure

내부 ICPM과 외부 PCPM은 `apps/caddy-proxy-manager`에 고정한 동일한 앱 소스와 이미지를 사용한다.
현재 기준은 **Caddy Proxy Manager v1.11.2**다.
앱은 별도 fork의 Git submodule이며, 인스턴스 설정과 운영 배포 파일만 이 저장소에서 관리한다.

```sh
git clone --recurse-submodules <infra-repository-url>
cd infra
./scripts/validate.sh
```

- `apps/caddy-proxy-manager`: 앱 fork의 고정 커밋
- `config/common`, `config/icpm`, `config/pcpm`: 공통/인스턴스별 비밀값 없는 설정
- `deployment`: 방화벽, Caddy, 관측기, 배포 스크립트와 비밀값 템플릿
- `scripts`: 검증, 공통 이미지 빌드, 앱 버전 고정, 오프라인 릴리스 생성
- `docs`: [운영 이전](docs/MIGRATION.ko.md), [업데이트](docs/UPDATE.ko.md), [Git 업로드](docs/GIT.ko.md)

서버 도메인/IP는 로컬 `.env`에서 읽고, 마운트할 정책은 `deployment/generated/`에 생성한다.
설정 방법은 [환경설정](docs/ENV.ko.md)을 따른다. 고정 Docker 네트워크와 서비스 분리는 유지한다.
기본 Compose 프로젝트 이름은 `cpm-preview`다. 운영의 `cpm`과 연결하기 전에 이전 문서를 따른다.
프로젝트 이름이 달라도 공개 포트와 고정 네트워크가 충돌하므로 같은 서버에서 병렬 실행하지 않는다.

실제 `.env`, `deployment/secrets/*.env`, DB, 인증서, 로그, 백업은 Git에 넣지 않는다.
기존 패치 파일은 이전 운영 디렉터리에 보존하며, 앞으로 Git 커밋을 변경 이력의 기준으로 사용한다.
