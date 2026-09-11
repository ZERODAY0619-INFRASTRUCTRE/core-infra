# Caddy Proxy Manager v1.11.2 적용

- 원본: https://github.com/fuomag9/caddy-proxy-manager.git
- 정식 릴리스: https://github.com/fuomag9/caddy-proxy-manager/releases/tag/v1.11.2
- 공개 시각: 2026-09-09 16:54:09 UTC
- 원본 커밋: `7e5791750e5f6bbd8444ed62c680b8df8ed7c05d`
- 확인 시점의 원본 기본 브랜치 `develop`도 같은 커밋이다.

기존 공통 앱 기준 `f1257934` 이후 두 원본 커밋을 merge로 반영했다.
Caddy Go 모듈의 gRPC pin이 1.83.1에서 1.83.2로 갱신됐고,
로그 회전/정리와 WAF 로그 비우기에 필요한 디렉터리·파일 권한 안내가 보강됐다.
추가 DB 마이그레이션은 없다. 기존 TOMORI UI, 인증 수정, 상태 화면,
오류 피드백, 분석 기능과 ICPM/PCPM 분리는 유지한다.

앱 `package.json`은 1.11.2로 맞춰 기본 빌드의 UI/OpenAPI가 1.0.0으로 표시되지 않도록 했다.
infra 빌드는 `1.11.2+tomori.<앱 커밋>`을 전달하고 두 이미지에 같은 버전/커밋 라벨을 붙인다.
이미지 태그는 기존처럼 앱 커밋으로 고정한다.

이 업데이트는 `git-ready`의 공통 앱 및 infra에 적용한다.
기존 운영 디렉터리·DB·실행 중인 서비스는 별도 전환 전까지 유지한다.
운영 전환 절차는 `MIGRATION.ko.md`를 따른다.

이미지 빌드 검증에서 upstream xcaddy가 go.mod의 gRPC 간접 pin을 전달하지 않는 것을 확인했다.
빌드 스크립트는 go.mod의 gRPC 버전을 읽어 명시적 replacement로 전달하도록 보정했다.
Dockerfile은 의존성 준비와 build.sh 복사를 분리해 이후 스크립트 변경 시 캐시를 재사용한다.
