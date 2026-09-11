# GitHub 업로드

업로드할 작업 디렉터리는 `/opt/infra/git-ready/publish/infra` 하나다.
원격은 `git@github.com:ZERODAY0619-INFRASTRUCTRE/core-infra.git`이다.
앱의 별도 원격이나 submodule 커밋을 먼저 올릴 필요가 없다.

```sh
cd /opt/infra/git-ready/publish/infra
python3 scripts/app-source.py prepare
python3 scripts/scan-publish.py
git status
# 변경이 있으면 검토한 파일만 추가하고 커밋한다.
git add patches scripts compose.yaml .env.example docs README.md
git commit -m "Update deployment and application patch"
git push -u origin main
```

Git에는 번호순 패치 시리즈, `upstream.json`, 배포 파일과 `.env.example`이 들어간다.
`apps/`와 실제 `.env`는 제외된다. SSH 인증은 push하는 환경에 설정되어 있어야 한다.
과거 앱 저장소와 백업을 통째로 업로드하지 않는다.

다른 서버와 CI는 일반 clone 뒤 공개 원본을 준비한다:

```sh
git clone git@github.com:ZERODAY0619-INFRASTRUCTRE/core-infra.git
cd core-infra
python3 scripts/app-source.py prepare
./scripts/validate.sh
```

CI checkout에는 `submodules: recursive`가 없다. 소스 준비가 실패하면 공개 원본 커밋 접근,
패치 체크섬, 패치 적용 충돌을 확인한다. 임의의 다른 커밋으로 대체하지 않는다.
