# 실행·평가 환경 재현성

## 변경 이유와 계약

mutable python:3.12-slim 태그는 같은 커밋의 다음 빌드에서 다른 기반 이미지를 선택할 수 있다. 실제 빌드에서 digest 변경과 의존성 재설치를 확인했다. 기존 requirements의 범위는 향후 다른 패키지 버전을 선택할 수도 있었다.

서비스별 requirements는 필요한 패키지와 지원 범위를 계속 정의한다. 공통 requirements-constraints.txt는 검증한 직접/전이 의존성의 선택 버전을 고정한다. 제약 파일은 모든 패키지를 설치하는 목록이 아니다. 서비스 requirements에 필요하지 않은 패키지는 설치되지 않는다. Windows pywin32와 Linux uvloop는 플랫폼 marker로 구분한다.

backend/frontend/legal_mcp/database-tools의 Python 기반 이미지는 검증한 digest sha256:eeb8088e67610b37583880c7627e3931f087cba55a35810819e34a398f624a47로 고정했다. 이 이미지에서 확인한 Python은 3.12.15다. CI는 ubuntu-24.04와 Python 3.12.15를 지정한다. PostgreSQL/Redis 서비스 버전과 기존 DB 볼륨은 변경하지 않는다.

## 설치와 확인

저장소 루트에서 Python 3.12 가상환경을 만든다. 기존 Windows Python을 전역으로 업그레이드하지 않는다.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe scripts/check_environment.py --output output/portfolio/environment.json
.\.venv\Scripts\python.exe -m pytest -q
```

Linux에서는 python 또는 python3 명령을 사용한다. 서비스 의존성만 직접 설치할 때는 루트에서 `python -m pip install -c requirements-constraints.txt -r backend/requirements.txt`처럼 제약 파일을 명시한다. 개발 requirements는 제약 파일을 자동 포함하며 Dockerfile도 같은 제약 파일을 복사해 사용한다. Windows pip의 한글 주석 디코딩 오류를 피하려고 database/requirements.txt에 UTF-8 선언을 추가했다.

check_environment.py는 Python 3.12 여부와 현재 설치된 배포 패키지의 고정 버전 일치를 검사한다. 제약에 없는 전이 의존성도 오류로 보고한다. pip/setuptools/wheel은 설치 도구로서 패키지 버전 검사에서 제외한다. 이 검사는 서비스 requirements에 있는 모든 패키지의 존재나 의존성 호환성을 대신 검증하지 않는다. 실제 설치와 pip check, 테스트를 함께 실행한다.

환경 JSON은 Python/OS, 설치 버전, 제약 파일 SHA-256과 오류 목록을 기록한다. API 키·환경변수·DB 연결 문자열·사용자 질문을 읽거나 저장하지 않는다. 성능/품질 실험 시 결과 옆에 환경 JSON을 저장해 비교 조건을 함께 남길 수 있다.

## 실제 검증 기록

| 환경 | 설치·환경 검사 | 테스트 |
| --- | --- | --- |
| 새 Windows 가상환경, Python 3.12.7 | 79개 배포 패키지, 제약 오류 없음, pip check 통과 | 실제 Redis/PostgreSQL 포함 388 passed, 4 skipped |
| 깨끗한 Linux 컨테이너, Python 3.12.15 | 77개 배포 패키지, 제약 오류 없음, pip check 통과 | 통합 연결 미지정: 378 passed, 12 skipped |
| 최종 환경 검증기 오류 처리 | 틀린 버전·누락한 pin·범위 제약을 거부 | 새 Windows 및 Linux 각각 3 passed |
| backend/frontend/MCP/database-tools 이미지 | 제약 적용 빌드 및 각 pip check 성공 | backend/frontend 건강 상태 HTTP 200, MCP protocol discovery 6개 도구, compose 전체 healthy |

전체 검사 이후 환경 검증기의 범위 제약 거부 사례 1개를 추가해 위 최종 관련 검사를 다시 실행했다. 같은 명령으로 실행하지 않은 결과를 하나의 전체 실행 수치로 합산하지 않는다.

[Windows 기존 환경](../output/portfolio/environment-windows.json) · [Windows 새 가상환경](../output/portfolio/environment-windows-clean.json) · [Linux 환경](../output/portfolio/environment-linux.json)

## 버전 갱신

1. 별도 가상환경에서 현재 서비스 requirements의 범위를 해석한다. 현재 제약 파일을 우회한 후보 설치는 기존 환경과 분리한다.
2. `python -m pip list --format=json`으로 후보 버전을 수집해 제약 파일을 갱신한다. Windows/Linux 전이 의존성을 모두 확인하고 플랫폼 marker를 유지한다. pip freeze의 로컬 경로·비공개 패키지 URL을 그대로 커밋하지 않는다.
3. 깨끗한 Windows 및 Linux 설치에서 pip check와 환경 검증을 통과시킨다. 신규 의존성이 제약에 없으면 누락을 수정한다.
4. 전체 테스트, Redis/PostgreSQL 통합 검사, 서비스 Docker 빌드와 건강 상태를 확인한다.
5. 기반 이미지를 갱신할 때는 registry digest와 컨테이너 Python 버전을 실제 확인하고 동일한 검증을 반복한다.

## 범위와 한계

버전 제약과 이미지 digest 고정은 wheel 다운로드 파일 해시 검증이나 오프라인 배포 묶음이 아니다. Windows/Linux의 플랫폼 의존성 및 OS/Python 패치가 다르므로 바이너리까지 동일한 환경이라고 주장하지 않는다. 실제 검사한 Windows Python은 3.12.7, Linux Docker는 3.12.15다. 다른 Python minor/CPU architecture 전체를 검증한 것은 아니다.

database-tools 빌드는 공통 제약 파일을 읽기 위해 저장소 루트 context로 변경했고 root .dockerignore의 비밀정보 제외 규칙을 적용한다. 배포 공유 폴더의 기존 릴리스 이미지나 Docker Hub 태그를 새로 게시하지 않는다. 이번 작업은 저장소에서 새로 설치/빌드하는 경로에 적용한다. 모델·embedding 유료 호출 없이 검증하며 응답 속도 향상 수치를 주장하지 않는다.
