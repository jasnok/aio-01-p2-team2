# LawPath 개인 포트폴리오용 Docker 실행

이 문서는 팀 서버 없이 한 대의 PC에서 LawPath를 실행하는 방법입니다. Docker Compose가 Frontend, Backend, Legal MCP, PostgreSQL + pgvector, Redis를 하나의 내부 네트워크로 연결합니다.

## 1. 사전 준비

- Docker Desktop을 실행하고 Linux containers 모드인지 확인합니다.
- OpenAI API Key를 준비합니다. 현재 MCP 검색 임베딩과 실제 입력 판단·답변 생성에 필요합니다.
- Python 설치는 컨테이너 실행에는 필요하지 않습니다. 법률 자료를 호스트에서 직접 적재할 때만 필요합니다.

현재 PC의 Wi-Fi 주소가 `192.100.200.232`이면 실행 후 Frontend는 `http://192.100.200.232:8501`에서 엽니다. 주소가 바뀌면 `backend/.env`의 `FRONTEND_ORIGIN`도 같은 주소로 바꿉니다.

## 2. 환경변수 준비

각 서비스의 예시 파일을 복사합니다. 루트 `.env`는 사용하지 않습니다. 이미 서비스별 `.env`가 있다면 덮어쓰지 말고 해당 파일에서 아래 값을 수정합니다.

```powershell
Copy-Item frontend/.env.example frontend/.env
Copy-Item backend/.env.example backend/.env
Copy-Item legal_mcp/.env.example legal_mcp/.env
Copy-Item database/.env.example database/.env
```

값은 아래처럼 맞춰야 합니다.

| 파일 | 반드시 확인할 값 |
|---|---|
| `database/.env` | PostgreSQL·Redis를 함께 생성하는 인프라 설정: `POSTGRES_PASSWORD`, `REDIS_PASSWORD`, `DATABASE_URL`, `OPENAI_API_KEY` |
| `backend/.env` | DB 비밀번호가 같은 `DATABASE_URL`, Redis 비밀번호가 같은 `REDIS_URL`, `OPENAI_API_KEY`, `FRONTEND_ORIGIN` |
| `legal_mcp/.env` | DB 비밀번호가 같은 `DATABASE_URL`, `OPENAI_API_KEY` |
| `frontend/.env` | 화면 타임아웃 등 Frontend 설정. Compose가 `BACKEND_API_URL=http://backend:8000`을 고정 주입 |

`DATABASE_URL`의 호스트는 Compose 내부 서비스명인 `postgres:5432`입니다. 비밀번호에 `@`, `:`, `/`, `?`, `#`를 넣었다면 URL 인코딩해야 하므로 영문·숫자·`-`·`_` 조합을 권장합니다. 네 파일의 실제 API Key·비밀번호는 Git에 올리지 않습니다.

## 3. 전체 서비스 실행

```powershell
docker compose config --quiet
docker compose up --build -d
docker compose ps
```

정상 포트는 다음과 같습니다.

| 서비스 | 브라우저 또는 로컬 접근 |
|---|---|
| Frontend | `http://192.100.200.232:8501` |
| Backend API 문서 | `http://192.100.200.232:8000/docs` |
| MCP | `http://192.100.200.232:8013/mcp` |
| PostgreSQL | 이 PC의 `127.0.0.1:5434` |
| Redis | 이 PC의 `127.0.0.1:6380` |

PostgreSQL·Redis는 인터넷 또는 같은 LAN의 다른 PC에 노출하지 않습니다. 앱 컨테이너는 내부 Compose 서비스명으로 연결합니다.

## 4. DB 초기화와 법률 자료 적재

빈 PostgreSQL 볼륨을 처음 만들면 `database/migrations/001`~`006` SQL이 자동 실행됩니다. 기존 볼륨에 후속 SQL을 자동 적용하지 않으며, 기존 DB·볼륨을 삭제하지 마세요.

법률 자료는 마이그레이션에 포함되지 않습니다. 저장소의 `database/raw/` 원본과 OpenAI Embedding API를 사용해 필요한 자료를 한 번 적재합니다. 다음은 실제 DB를 변경하고 API 비용이 발생하는 명령입니다.

```powershell
# 법령
docker compose --profile tools run --rm database-tools python scripts/ingest_laws.py --load-db --with-embeddings

# 판례: 분야별로 실행
docker compose --profile tools run --rm database-tools python scripts/ingest_cases.py --source all --category housing --only-new --load-db --with-embeddings
docker compose --profile tools run --rm database-tools python scripts/ingest_cases.py --source all --category labor --only-new --load-db --with-embeddings
docker compose --profile tools run --rm database-tools python scripts/ingest_cases.py --source all --category consumer --only-new --load-db --with-embeddings

# 소비자 상담사례
docker compose --profile tools run --rm database-tools python scripts/ingest_consumer.py --load-db --with-embeddings
```

적재 전후에는 [DB 스크립트 안내](../database/scripts/README.md)와 원문 자료의 이용 조건을 확인하세요. 개인 포트폴리오 DB에는 팀의 회원·질의 이력·대화 데이터를 복사하지 않습니다.

## 5. 상태·로그 확인

```powershell
docker compose ps
docker compose logs -f backend
docker compose logs -f mcp-server
Invoke-WebRequest http://127.0.0.1:8000/health
```

대표 질문을 Frontend에서 실행해 SSE 진행 표시, 결과 카드, 법령·판례·상담사례의 실제 반환을 확인합니다. `docker compose ps`의 healthy는 프로세스·기본 HTTP 연결 상태이며 검색 품질이나 자료 적재 완료를 보장하지 않습니다.

## 6. 종료와 재빌드

```powershell
docker compose down
docker compose up --build -d
```

`docker compose down -v`는 PostgreSQL·Redis의 영속 볼륨을 삭제하므로, 새 개인 DB를 의도적으로 초기화하는 경우에만 사용합니다.

## 7. Docker Hub·AWS 확장

현재 Compose는 로컬 `build`를 사용합니다. 배포 단계에서는 `frontend`, `backend`, `mcp-server` 이미지에 Registry 이름과 커밋 태그를 부여하고 GitHub Actions에서 빌드·푸시한 뒤 AWS에서 같은 Compose 파일을 `image:` 기준으로 실행합니다. DB 비밀번호·OpenAI Key는 이미지 또는 GitHub 저장소에 넣지 않고 배포 환경의 Secret으로 전달합니다.

AWS, Docker Hub, GitHub Actions 배포는 이 문서 작성 시점에 구성·검증하지 않았습니다.
