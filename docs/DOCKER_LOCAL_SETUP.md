# LawPath 개인 포트폴리오용 Docker 실행

이 문서는 팀 서버 없이 한 대의 PC에서 LawPath를 실행하는 방법입니다. Docker Compose가 Frontend, Backend, Legal MCP, PostgreSQL + pgvector, Redis를 하나의 내부 네트워크로 연결합니다.

## 1. 사전 준비

- Docker Desktop을 실행하고 Linux containers 모드인지 확인합니다.
- OpenAI API Key를 준비합니다. 현재 MCP 검색 임베딩과 실제 입력 판단·답변 생성에 필요합니다.
- Python 설치는 컨테이너 실행에는 필요하지 않습니다. 법률 자료를 호스트에서 직접 적재할 때만 필요합니다.

로컬 촬영은 `http://localhost:8501`에서 진행합니다. `backend/.env`의 `FRONTEND_ORIGIN`도 같은 주소로 설정합니다. LAN 접속이 필요하면 해당 PC 주소를 별도로 설정합니다.

## 2. 환경변수 준비

각 서비스의 예시 파일을 복사합니다. 루트 `.env`는 이미지 이름·태그 지정용이며, API 키와 연결 비밀번호는 서비스별 `.env`에 둡니다. 이미 서비스별 `.env`가 있다면 덮어쓰지 말고 해당 파일에서 아래 값을 수정합니다.

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
| Frontend | `http://localhost:8501` |
| Backend API 문서 | `http://localhost:8000/docs` |
| MCP | `http://localhost:8013/mcp` |
| PostgreSQL | 이 PC의 `127.0.0.1:5434` |
| Redis | 이 PC의 `127.0.0.1:6380` |

PostgreSQL·Redis는 인터넷 또는 같은 LAN의 다른 PC에 노출하지 않습니다. 앱 컨테이너는 내부 Compose 서비스명으로 연결합니다.

## 4. DB 초기화와 법률 자료 적재

빈 PostgreSQL 볼륨을 처음 만들면 마이그레이션 후 `database/seed/010_legal_search_data.sql.gz`가 자동 복원됩니다. 검색 문서 702건과 임베딩 청크 2,797건이 포함되므로 기본 시연을 위해 원문을 다시 적재할 필요는 없습니다.

기존 볼륨은 덮어쓰거나 자동 갱신하지 않습니다. 먼저 현재 검색 문서와 청크 수를 확인합니다. 추가 자료를 적재할 때에만 [DB 스크립트 안내](../database/scripts/README.md)를 따릅니다. 개인 포트폴리오 DB에는 팀의 회원·질의·대화 데이터를 복사하지 않습니다.

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

## 8. 개인 리팩토링 평가와 촬영

- 검색 가중합은 기본값이며 `RETRIEVAL_FUSION=rrf`로 순위 결합을 비교할 수 있습니다.
- `RETRIEVAL_FILTER_ENABLED=false`가 기본값입니다. 기존 임계값 0.5는 검토된 정답 근거로 보정한 값이 아니므로 바로 활성화하지 않습니다. 검색 점수는 정답 확률이 아닙니다.
- 동일 질의 임베딩은 모델·차원·인증 설정별로 최대 128개, 5분간 메모리 캐시합니다. 동시에 시작된 최초 호출은 중복될 수 있으며 공유 Redis 캐시는 아닙니다.
- 답변 상태는 `generation_status`, 사용한 근거는 `used_evidence_ids`·`cited_claims`, 소요 시간과 생성 토큰은 `diagnostics`에서 확인합니다. 인용문 존재 검사는 법률적 타당성 검증과 다릅니다.
- 실제 실행 결과와 SSE 이벤트는 Redis에 24시간 보관합니다. 같은 소유자의 동일 요청 키는 중복 실행하지 않습니다. 기본 전체 실행 제한은 150초입니다. API 재시작 후 완료 결과는 조회할 수 있지만 진행 중 작업 자체는 재개하지 않습니다. 중단 상태는 제한 시간 이후 조회 시 실패로 표시합니다.

실제 서버의 4개 시나리오 확인(LLM 비용 발생, 비회원 임시 이력 생성):

```powershell
.venv/Scripts/python -X utf8 scripts/portfolio_smoke.py --output output/portfolio/after-smoke.json
```

로컬 회귀 테스트는 실제 API 호출과 분리합니다.

```powershell
./scripts/test_all.ps1
```

촬영 순서(약 3분): 개인 기여 소개 20초 → 대표 질문 입력과 SSE 50초 → 답변·인용 원문 확인 35초 → 정보 부족 질문 25초 → PDF·이력 20초 → 개선 비교와 한계 30초. 근거가 명확한 질문을 리허설해 선택하고, 답변 생성 실패 안내도 정상 생성 화면과 구분합니다. 대기 구간을 편집하면 자막으로 표시합니다. API 키·세션 토큰은 촬영 화면에 포함하지 않습니다.

검색 평가는 `tests/portfolio_dataset.py`의 30건으로 진행합니다. 15건은 데이터 스냅샷의 법령명·사건번호 조회이며, 나머지 15건은 자연어 관련성 검토용입니다. 식별자 조회 성공률을 법률 정답률로 발표하지 않습니다. 자연어 검색과 답변 품질은 근거 원문을 사람이 검토한 뒤 별도로 기록합니다.

### 검색 비교 재현

기준선 소스는 `output/portfolio/baseline_retrieval.py`와 `baseline_repository.py`에 보관했습니다. 아래 명령은 질문 30건의 임베딩 API 비용을 발생시킬 수 있습니다. 최종 답변 생성은 호출하지 않습니다.

```powershell
docker compose cp scripts mcp-server:/app/
docker compose cp tests mcp-server:/app/
docker compose cp output/portfolio/baseline_retrieval.py mcp-server:/app/baseline_retrieval.py
docker compose cp output/portfolio/baseline_repository.py mcp-server:/app/baseline_repository.py
docker compose exec -T mcp-server python scripts/evaluate_portfolio_retrieval.py --baseline /app/baseline_retrieval.py --baseline-repository /app/baseline_repository.py --output /app/retrieval-comparison.json
docker compose cp mcp-server:/app/retrieval-comparison.json output/portfolio/retrieval-comparison.json
```

SQL 단독 비교는 `scripts/benchmark_keyword_search.py --baseline /app/baseline_repository.py --output /app/keyword-benchmark.json`으로 같은 MCP 컨테이너에서 실행합니다. 검색 비교의 소요 시간은 임베딩을 재사용한 상태에서 측정한 검색 시간이며 사용자 체감 전체 지연 시간과 구분합니다.
