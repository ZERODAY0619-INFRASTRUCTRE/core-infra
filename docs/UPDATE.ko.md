# 원본 업데이트와 릴리스

## 앱 업데이트

Bun 1.4.2와 Node 24를 사용한다. 현재 Vitest 5와 better-sqlite3 13은 Node 20을 지원하지 않는다.

앱 fork의 `custom/main`은 배포 커스텀 이력을 유지한다. 원본 갱신은 별도 브랜치에서 한다.

```sh
cd ../caddy-proxy-manager
git switch custom/main
git fetch upstream
git switch -c update/<version>
git merge <reviewed-upstream-tag-or-commit>
bun install --frozen-lockfile --ignore-scripts
bun run test --maxWorkers=1
sh scripts/test-custom.sh
bun run typecheck
DATABASE_URL=file:/tmp/cpm-build.db DATABASE_PATH=/tmp/cpm-build.db bun --bun run build
```

병합한 릴리스에 맞춰 앱 `package.json`의 version과 `CUSTOMIZATIONS.md`의 원본 기준을 갱신한다.
충돌은 커스텀 기능의 의도를 보존해 해결한다. 인증/DB 마이그레이션/Caddy pin 변경은 별도 검토한다.
테스트 후 앱 브랜치를 리뷰·병합·push하고, infra에서 그 커밋을 고정한다.

```sh
cd ../infra
git -C apps/caddy-proxy-manager fetch origin
./scripts/update-app.sh <approved-app-commit>
./scripts/build.sh
git diff --cached --submodule=log
git commit -m "Update common CPM application"
```

두 이미지 태그는 앱 커밋으로 생성되며, UI/OpenAPI 및 이미지 라벨에는 `1.11.2+tomori.<commit>` 형태의 버전을 기록한다.
`./scripts/build.sh web` 또는 `caddy`로 한 구성 요소만 빌드할 수 있다.
이 서버처럼 BuildKit bridge DNS가 동작하지 않는 환경은 `CPM_BUILD_NETWORK=host`를 빌드에만 지정한다.
두 이미지 태그는 앱 커밋으로 생성된다. 빌드 스크립트 출력대로 `.env`의 이미지 태그를 갱신한다.
빌드는 컨테이너를 재시작하지 않는다. 실제 전환 전 DB 백업과 변경된 DB 스키마의 호환성을 확인한다.
이전 Git 커밋/이미지만 되돌려도 DB 마이그레이션은 되돌아가지 않는다. 필요하면 이전 DB 백업을 복원한다.

## 오프라인 소스 릴리스

```sh
./scripts/package-release.sh
```

깨끗한 커밋 상태에서 `artifacts/infra-<commit>/`에 두 Git bundle, 통합 소스 tarball,
커밋 메타데이터와 SHA256SUMS를 만든다. 빌드 이미지와 의존성은 별도 전달한다.
예전 단일 Python 패치 설치기를 새 디렉터리에 적용하지 않는다.
소스 tarball은 Git 메타데이터가 없는 열람/빌드용 export이며 Git 기반 검증/업데이트에는 bundle을 복원한다.

```sh
git clone caddy-proxy-manager.bundle caddy-proxy-manager
git -C caddy-proxy-manager switch -c custom/main
git -C caddy-proxy-manager remote add upstream https://github.com/fuomag9/caddy-proxy-manager.git
git clone infra.bundle infra
git -C infra switch -c main
# 로컬 bundle 복원에만 file 전송을 명시적으로 허용한다.
git -C infra -c protocol.file.allow=always submodule update --init
```
