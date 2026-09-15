# LawPath 공개 검색 데이터 스냅샷

- 데이터 버전: 2026-09-14
- 포함 범위: `legal_documents`, `legal_chunks`
- 제외 범위: 사용자, 인증 정보, 질의/저장 이력, Redis 데이터, 환경변수와 API 키
- 법령 문서: 8건
- 판례 문서: 16건
- 소비자 상담사례 문서: 678건
- 전체 문서: 702건
- 전체 청크: 2,797건
- 임베딩 누락 청크: 0건
- 임베딩 모델: `text-embedding-3-small`
- 벡터 차원: 1,536
- 스냅샷 SHA-256: `CD741259E8CAEB8CB73AA1A91EFB38C4756E2B71F470680E0612CF8C9E004647`

`010_legal_search_data.sql.gz`는 현재 검증된 개인 PostgreSQL DB에서 공개 검색 테이블만 export한 스냅샷이다. 새 Docker volume에서 PostgreSQL 초기화 시 migration 다음에 자동 복원된다.
