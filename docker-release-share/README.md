# LawPath Docker 공유 폴더 안내

이 폴더는 Docker Hub 릴리스 이미지를 이용해 다른 컴퓨터에서 LawPath를 실행하고, 현재 검증된 실제 법령·판례·소비자 상담사례 검색 데이터를 재현하기 위한 배포 묶음입니다.

## 가장 빠른 실행 방법

1. Docker Desktop을 설치합니다.
2. 서비스별 `.env.example`을 `.env`로 복사하고, PostgreSQL·Redis 비밀번호와 OpenAI API 키를 입력합니다.
3. 루트 `.env.example`을 `.env`로 복사합니다. 기본 Docker Hub 계정은 `jso4603`, 이미지 태그는 `1.0.0`입니다.
4. 아래 명령을 실행합니다.

```powershell
docker compose -f compose.release.yml pull
docker compose -f compose.release.yml up -d
docker compose -f compose.release.yml ps
```

5. 브라우저에서 `http://localhost:8501`을 엽니다.

상세한 환경변수 설정, 실제 DB 데이터 확인, 초기화 주의사항은 [DOCKER_RELEASE.md](DOCKER_RELEASE.md)를 참고합니다.

## 포함 파일

- `compose.release.yml`: Docker Hub 이미지를 받아 실행하는 파일
- `compose.yml`: 전체 소스 저장소에서 로컬 이미지를 빌드할 때 사용하는 파일
- `database/seed/010_legal_search_data.sql.gz`: 실제 공개 검색 데이터와 임베딩 스냅샷
- 서비스별 `.env.example`: 비밀값 없이 필요한 환경변수만 안내

> `compose.yml`은 Dockerfile과 애플리케이션 소스 전체가 있는 원본 저장소에서 사용합니다. 이 공유 폴더만으로 실행할 때는 `compose.release.yml`을 사용하세요.
