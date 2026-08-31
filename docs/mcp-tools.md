# MCP Tool Contract

## `search_legal_documents`

- 목적: 자연어 상황으로 관련 법령과 사례를 검색한다.
- 사용: 사용자가 일상 언어로 법률 상황을 설명한 경우.
- 금지: 정확한 법령·조문 한 건을 조회하는 경우.
- 입력: `query`, `category`, `document_types`, `top_k`
- 출력: 공통 Tool envelope 안의 LegalDocument 목록

## `get_law_article`

- 목적: 정확한 법령명과 조문 번호의 원문을 조회한다.
- 구현 예정 담당: MCP

## `get_case_detail`

- 목적: 검색 결과의 문서 ID로 사건 상세를 조회한다.
- 구현 예정 담당: MCP

현재 `search_legal_documents`만 LAN 연결 검증용 Mock으로 구현되어 있다.

