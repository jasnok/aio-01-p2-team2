# Docker Hub 릴리스와 실제 검색 데이터 재현

## 포함되는 데이터

`lawpath-postgres` 이미지에는 현재 검증된 공개 검색 데이터만 포함됩니다.

- 법령 8건, 판례 16건, 소비자 상담사례 678건
- `legal_documents`, `legal_chunks`, pgvector 임베딩
- 사용자·질의 이력·API 키·비밀번호는 포함하지 않음

상세 버전과 점검 수치는 [DATA_MANIFEST](../database/seed/DATA_MANIFEST.md)를 확인합니다.

## 배포 전 준비

1. 각 서비스의 `.env.example`을 복사해 실제 `.env`를 만듭니다.
2. `backend/.env`, `legal_mcp/.env`에 실제 `OPENAI_API_KEY`를 설정합니다.
3. 루트 `.env.example`을 `.env`로 복사하고 Docker Hub 계정명과 배포 태그를 설정합니다.

```ini
DOCKERHUB_NAMESPACE=jso4603
IMAGE_TAG=1.0.0
```

루트 `.env`에는 Docker Hub 이미지 정보만 두며, API 키·비밀번호는 넣지 않습니다.

## 이미지 빌드와 업로드

```powershell
docker login
docker compose -f compose.yml build
docker compose -f compose.yml push postgres mcp-server backend frontend
```

## 다른 PC에서 실행

저장소와 서비스별 `.env`를 준비한 뒤 다음을 실행합니다.

```powershell
docker compose -f compose.release.yml pull
docker compose -f compose.release.yml up -d
docker compose -f compose.release.yml ps
```

처음 실행할 때는 빈 Docker volume에 migration과 실제 검색 데이터 seed가 자동 복원됩니다. 기존 `lawpath-postgres-data` volume이 있다면 그 DB를 유지하므로 seed를 다시 적용하지 않습니다.

## 확인 방법

```powershell
Invoke-WebRequest http://127.0.0.1:8000/health
docker compose -f compose.release.yml exec postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT document_type, count(*) FROM legal_documents GROUP BY document_type ORDER BY document_type;"'
```

정상 값은 `LAW 8`, `CASE 16`, `CONSULTATION 678`입니다. 이후 브라우저에서 `http://localhost:8501`을 열고 대표 소비자 질문을 실행하면 법령·판례·상담사례가 각각 3건씩 표시됩니다.

> 새 Docker volume에서 재현을 확인하려면 실행 중인 서비스가 없는지 확인한 뒤 `docker compose -f compose.release.yml down -v`를 사용합니다. 이 명령은 해당 Compose의 DB·Redis 볼륨을 삭제합니다.
