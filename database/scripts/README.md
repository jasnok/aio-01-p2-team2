# Database Scripts

법률 데이터 수집·적재·임베딩·검색 검증을 실행하는 스크립트 모음입니다. 전체 구조와 담당 범위는 [상위 README](../README.md)를 참고합니다.

## 1. 실행 준비

아래 명령은 `database` 디렉터리에서 실행합니다.

```powershell
cd C:\miniProject\aio-01-p2-team2\database
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

가상환경이 없다면 활성화 전에 `python -m venv .venv`로 생성합니다. `.env.example`을 참고하여 `database/.env`를 설정합니다.

| 환경변수 | 필요한 작업 |
|---|---|
| `DATABASE_URL` | 적재·검색·기존 자료 비교 |
| `OPENAI_API_KEY` | 문서·질문 임베딩 |
| `EMBEDDING_MODEL` | `text-embedding-3-small` |
| `EMBEDDING_DIMENSION` | `1536` |
| `LAW_API_BASE_URL`, `LAW_API_OC` | 공식 법률 API 수집 |

비밀번호·API Key는 Git에 올리지 않습니다. 일부 스크립트는 루트 `.env`를 먼저 읽고 `database/.env`로 덮어쓰므로 접속 대상 설정을 확인합니다.

## 2. 스크립트 목록

| 파일 | 역할 |
|---|---|
| `collect_laws_once.py` | 지정 법령 XML 수집 |
| `collect_cases_once.py` | 지정 판례 XML 수집 |
| `ingest_laws.py` | 법령 정규화·적재·임베딩 |
| `ingest_cases.py` | API XML·PDF 판례 정규화·적재·임베딩 |
| `ingest_consumer.py` | 소비자 피해구제 사례 적재 |
| `ingest_labor_decisions.py` | 노동위원회 판정자료 처리 |
| `audit_case_texts.py` | 판례 본문 품질 검사 |
| `search_laws.py` | 법령 Hybrid 검색 |
| `search_consumer.py` | 소비자 피해구제 검색 |
| `search_all.py` | 법령·판례·소비자 사례 유형별 벡터 검색 |
| `inspect_saved_conversations.py` | 저장 대화 점검 |
| `saved_conversation_queries.sql` | 저장 대화 확인용 SQL |

옵션을 제공하는 스크립트는 `--help`로 사용법을 확인합니다.

```powershell
python scripts/ingest_cases.py --help
```

## 3. 원본 수집

```powershell
python scripts/collect_laws_once.py
python scripts/collect_cases_once.py
```

원본 저장 위치:

```text
database/raw/api/laws/
database/raw/api/cases/{category}/
```

수집은 DB 적재·임베딩을 수행하지 않습니다. 기존 원본은 기본적으로 건너뛰며 법령 수집은 collection manifest도 기록합니다. 건너뛴 파일의 현행성까지 재검증하는 것은 아닙니다.

현재 `collect_cases_once.py`의 `CASE_TARGETS`는 확보된 전체 판례와 일치하지 않습니다. Consumer 목록과 Housing 누락 ID를 보완해야 전체 원본을 재현할 수 있습니다.

## 4. 판례 품질 검사

전체 원본 검사:

```powershell
python scripts/audit_case_texts.py --source all
```

특정 카테고리 PDF 검사:

```powershell
python scripts/audit_case_texts.py --source files --category housing
```

| 출력 | 의미 |
|---|---|
| 정상 | 검사 패턴에서 공백 의심을 발견하지 않음 |
| 검토 필요 | 정상 문장·표 또는 추출 오류일 수 있어 문맥 확인 필요 |
| 추출·파싱 실패 | 원본 처리 오류 해결 필요 |

검사는 DB를 변경하거나 임베딩을 생성하지 않습니다. 정규화 본문이 검사 대상이며 청크 생성 후 발생하는 문제·표 구조·검색 정확도까지 보장하지 않습니다.

## 5. 판례 적재

처리 대상 확인:

```powershell
python scripts/ingest_cases.py --source files --category housing --only-new
```

적재·임베딩:

```powershell
python scripts/ingest_cases.py `
  --source files `
  --category housing `
  --only-new `
  --load-db `
  --with-embeddings
```

완료 후 대상 확인 명령을 다시 실행합니다. Labor·Consumer는 `--category`를 각각 `labor`, `consumer`로 변경합니다.

```text
신규 판례: 0건
본문 변경 판례: 0건
Embedding 미완료 판례: 0건
최종 처리 대상: 0건
```

| 옵션 | 의미 |
|---|---|
| `--source files` | 확보한 PDF 판례 |
| `--source api` | 저장된 API 판례 XML |
| `--source all` | PDF·API XML 모두 처리, 기본값 |
| `--category` | housing/labor/consumer, 생략하면 전체 |
| `--only-new` | 신규·본문 변경·청크 또는 임베딩 미완료 문서 선별 |
| `--load-db` | 실제 DB 저장 |
| `--with-embeddings` | 임베딩 생성, 판례는 `--load-db`와 함께 사용 |

`--only-new` 대상 확인도 DB 연결이 필요합니다. 모델·청크 정책 변경까지 모두 감지하지 않으므로 해당 변경 시 별도 재적재 계획이 필요합니다. 이 옵션은 모든 적재 스크립트에 공통으로 지원되는 옵션이 아닙니다.

## 6. 법령·소비자 사례 적재

특정 법령 확인:

```powershell
python scripts/ingest_laws.py --law "주택임대차보호법"
```

법령 적재·임베딩:

```powershell
python scripts/ingest_laws.py `
  --law "주택임대차보호법" `
  --load-db `
  --with-embeddings
```

`--law`를 반복하면 여러 법령을 지정할 수 있고, 생략하면 등록된 전체 대상 법령을 처리합니다.

소비자 피해구제 5건 확인:

```powershell
python scripts/ingest_consumer.py --limit 5
```

소비자 피해구제 전체 적재·임베딩:

```powershell
python scripts/ingest_consumer.py --load-db --with-embeddings
```

법령·소비자 적재에는 현재 `--only-new`가 없습니다. 반복 실행하면 임베딩 API가 다시 호출될 수 있습니다.

노동위원회 CSV는 상세 판정문이 없는 색인 자료입니다. `ingest_labor_decisions.py` 사용 시 본문 보유 여부와 근거 사용 제한 정책을 먼저 확인합니다.

## 7. 검색 검증

법령 Hybrid 검색:

```powershell
python scripts/search_laws.py `
  --query "임대차 계약이 끝났는데 보증금을 돌려받지 못했습니다." `
  --category housing `
  --top-k 3
```

소비자 피해구제 검색:

```powershell
python scripts/search_consumer.py `
  --query "구매한 물건이 배송되지 않아 환불받고 싶습니다." `
  --top-k 3
```

유형별 통합 벡터 검색:

```powershell
python scripts/search_all.py `
  --query "중고거래 판매자가 돈을 받고 물건을 보내지 않습니다." `
  --category consumer `
  --top-k-per-type 3 `
  --threshold 0.20
```

확인 항목은 질문 관련성, category·document_type, 출처 URL, 문서 중복입니다.

- 검색은 질문 임베딩을 위해 OpenAI API를 호출합니다.
- `search_all.py`는 유형별 최대 3개이며 전체 Top 3와 다릅니다. 현재 `ADMIN_DECISION`은 제외합니다.
- `search_laws.py` Threshold는 결합 점수, `search_all.py` Threshold는 벡터 유사도 기준입니다.
- Legal MCP의 실제 서비스 검색은 별도 경로로 검증합니다.

## 8. 실행 시 주의사항

- PowerShell 백틱 줄바꿈 뒤에 공백을 넣지 않습니다.
- `--only-new`는 공백 없이 입력합니다.
- 패키지 오류는 가상환경 활성화·의존성 설치를 확인합니다.
- 공백 경고는 문맥을 검토하고 실제 오류는 수정 후 재임베딩합니다.
- PDF 파일명은 법원·선고일·사건번호 파싱과 문서 식별에 영향을 줍니다.
- 적재 오류 시 실패 지점·DB 상태를 확인한 뒤 재실행합니다.
- 판례에서 `--load-db` 없이 실행하면 DB는 변경하지 않습니다. 이를 모든 스크립트의 외부 API 호출 여부까지 동일하다고 해석하지 않습니다.

## 9. 후속 작업

- Migration 실행기·적용 이력 관리 및 DB 통합 검증.
- `ingestion_runs` 실행 기록 연결.
- 판례 수집 대상 목록 보완.
- 노동 판정자료 근거 사용 제한.
- 최종 청크까지 포함하는 품질 감사 및 15문항 검색 평가.

현재 `migrate.py`, `verify_database.py`, `seed.py`는 구현된 명령으로 안내하지 않습니다. 구현 후 사용법을 추가합니다.
