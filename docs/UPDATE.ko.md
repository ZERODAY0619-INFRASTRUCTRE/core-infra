# 원본과 패치 업데이트

`patches/caddy-proxy-manager/upstream.json`에 공식 원본 URL·커밋·버전,
각 패치 SHA-256과 적용 후 Git 트리를 고정한다. `series` 순서대로 번호 패치를
`git am`으로 적용하며 바이너리와 파일 추가·삭제도 포함한다. 기존 커스텀 앱 소스와 동일한 결과로 검증했다.
라이선스 파일의 줄바꿈/공백은 원본 그대로 보존한다.

## 커스텀 변경 저장

```sh
python3 scripts/app-source.py prepare
# apps/caddy-proxy-manager 아래 필요한 소스를 수정한다.
git -C apps/caddy-proxy-manager add <수정한파일>
git -C apps/caddy-proxy-manager commit
# 제목: subsystem: imperative summary / 본문: 변경 이유와 동작
python3 scripts/app-source.py export
python3 scripts/app-source.py check
python3 scripts/scan-publish.py
git add patches/caddy-proxy-manager
git commit -m "Update CPM custom patch"
```

생성 소스에는 패치별 로컬 커밋이 생긴다. 변경도 앱 디렉터리에서 기능별로 커밋한 뒤
export한다. 기존 패치를 다듬을 때는 로컬 커밋을 수정하고 전체 시리즈를 다시 export한다. 앱 디렉터리의 수정만으로는 배포 저장소에
저장되지 않으며 반드시 export해야 한다. 체크섬을 수동으로 맞추는 대신 export를 사용한다.
준비된 소스의 변경은 자동으로 버리지 않는다. 다시 만들려면 `prepare --replace`를 사용하며,
이전 소스는 Git 제외 경로인 `deployment/backups/`로 이동해 보존한다.

## 원본 버전 올리기

```sh
python3 scripts/app-source.py prepare
./scripts/update-app.sh <검토한_공식_태그_또는_커밋>
```

도구는 `apps/cpm-update-*`라는 별도 작업 폴더에서 원본을 받고 기존 패치를 적용한다.
충돌은 해당 폴더에 남겨 직접 해결한다. 기존 준비 소스와 패치는 그대로 보존된다.
충돌 해결 후 `git add`와 `git am --continue`로 이어간다. 버전에 맞춘 추가 수정은
앱 `package.json`과 커스텀 문서를 포함해 기능별로 커밋한다.

```sh
# PATH는 도구가 출력한 업데이트 작업 폴더다.
git -C PATH add <검토한파일>
git -C PATH commit
python3 scripts/app-source.py export --source PATH --base <공식_전체_커밋_SHA> --version <버전>
python3 scripts/app-source.py prepare --replace
./scripts/validate.sh
```

앱 변경 검증에는 Bun 1.4.2와 Node 24를 사용한다. 앱 폴더에서 frozen lockfile 설치,
`bun run test --maxWorkers=1`, `sh scripts/test-custom.sh`, `bun run typecheck`,
임시 DB를 지정한 `bun --bun run build`를 수행한다. 인증·DB 마이그레이션·Caddy pin 변경은
별도로 검토한다. 테스트 후 패치와 원본 lock 파일을 같은 배포 커밋으로 올린다.

## 빌드와 릴리스

`./scripts/build.sh`는 소스를 준비·검증하고 공통 web/caddy 이미지를 만든다.
이미지 태그에는 적용 후 소스 트리의 앞 12자리를 사용한다. 출력된 태그를 `.env`에 입력한다.
`CPM_BUILD_NETWORK=host`는 필요할 때 빌드에만 적용한다. 빌드는 운영 서비스를 재시작하지 않는다.

`./scripts/package-release.sh`는 깨끗한 커밋에서 검사를 통과한 뒤 `artifacts/infra-<commit>/`에
배포 Git bundle 하나, 패치 포함 source.tar.gz, 메타데이터와 SHA256SUMS를 만든다.
앱 소스와 의존성·이미지는 포함하지 않는다. 복원 후 `app-source.py prepare`로 원본을 받는다.
망이 없는 환경에서는 원본 커밋을 가진 로컬 Git 저장소를 `prepare --source /path/to/repo`로 지정한다.

```sh
git clone infra.bundle infra
cd infra
python3 scripts/app-source.py prepare
```
