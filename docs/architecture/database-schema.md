# Database 계약

초기 Schema는 `database/migrations/001_init.sql`에 있습니다.

| 테이블 | 용도 |
|---|---|
| `users` | 익명 사용자 식별 |
| `legal_documents` | 공식 법령·판례 원문과 메타데이터 |
| `legal_chunks` | 검색용 Chunk와 1,536차원 Embedding |
| `ingestion_runs` | 수집 실행 이력 |
| `saved_conversations` | 사용자가 명시적으로 저장한 대화 |
| `saved_messages` | 저장 대화의 메시지 |
| `saved_message_sources` | 답변과 근거 연결 |

외부 자료는 `UNIQUE(source_name, external_id)`로 식별하고 `content_hash`가 변경됐을 때만 문서와 Chunk를 갱신합니다.

현재 개발 DB가 이전 `001_init.sql`로 이미 만들어졌다면 스키마가 자동 변경되지 않습니다. 중요한 데이터가 없는 개발 환경에서만 볼륨을 다시 만들거나, 데이터를 유지해야 한다면 후속 Migration을 작성합니다.
