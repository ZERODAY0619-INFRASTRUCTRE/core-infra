# Git 저장소 업로드

업로드용 로컬 작업 공간은 `git-ready/publish/` 아래 형제 디렉터리 `infra/`, `caddy-proxy-manager/` 두 개다.
앱 fork는 원본 커밋 이력을 보존하며 `upstream`만 원본 GitHub에 연결되어 있다.
infra의 `.gitmodules`는 `../caddy-proxy-manager`를 사용한다. 같은 소유자 아래 이 이름으로
두 원격 저장소를 만들면 clone 시 같은 서버의 형제 저장소로 해석된다.
이름/소유자가 다르면 `.gitmodules`의 URL을 실제 앱 fork 주소로 바꾸고 커밋한다.

배포 저장소는 환경변수 기반 파일로 새로 만든 최초 커밋부터 시작한다.
기존 작업 저장소의 이력은 별도로 보존되어 있으므로 업로드 대상에 포함하지 않는다.
업로드 전 `python3 scripts/scan-publish.py`로 현재 파일과 이력을 다시 확인한다.

GitHub에는 앱 fork와 배포 저장소 두 개를 만든다. 배포 저장소의 파일은 한 폴더에 모여 있고,
실제 환경설정은 그 루트의 `.env` 하나다. Git에는 `.env.example`만 올린다.
`apps/caddy-proxy-manager`는 앱 파일을 중복 업로드하는 대신 앱 fork의 커밋을 가리킨다.

배포 원격: `git@github.com:ZERODAY0619-INFRASTRUCTRE/core-infra.git`

앱 원격 주소가 정해진 뒤 실행할 명령(아직 push하지 않음):

```sh
cd ../caddy-proxy-manager
git remote add origin <APP_FORK_URL>
git push -u origin custom/main
cd ../infra
git remote add origin git@github.com:ZERODAY0619-INFRASTRUCTRE/core-infra.git
git push -u origin main
```

앱 저장소의 기본 브랜치는 `custom/main`으로 지정한다. 앱 커밋을 먼저 올린 뒤 infra를 올린다.
앱의 기존 upstream 자동 병합/이미지 게시 워크플로는 `.github/upstream-workflows/`에 보존하고
자동 실행 대상에서는 제외했다. 원본 테스트가 참조하는 Caddy pin 워크플로 경로는 유지하되 job을 `if: false`로 비활성화했다. 새 `custom-ci.yml`은 테스트·타입 검사·웹 빌드만 수행한다.

비공개 저장소의 submodule CI는 별도 읽기 권한이 필요하다. 저장소 토큰을 소스에 쓰지 않는다.
현재 Git 작성자 `Infra Migration <infra-migration@localhost>`는 로컬 이전 작업용 식별자다.

다른 서버에서는 배포 저장소 한 번만 clone하면 앱도 함께 내려받는다:

```sh
git clone --recurse-submodules git@github.com:ZERODAY0619-INFRASTRUCTRE/core-infra.git infra
cd infra
umask 077
cp .env.example .env
# .env 하나에 모든 실제 값을 입력한다.
./scripts/validate.sh
```

GitHub 웹의 파일 업로드 기능 대신 Git push를 사용해야 submodule 커밋 연결이 보존된다.
