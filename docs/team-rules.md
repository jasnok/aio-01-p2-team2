# Team Rules

## Branches

- `main`: 발표 가능한 버전
- `develop`: 통합 버전
- `feature/frontend-local-mvp`: 상옥 Frontend
- `feature/backend-agent-runtime`: 다혁 Backend·Agent
- `feature/mcp-legal-search-tools`: 병훈 Legal MCP
- `feature/db-legal-ingestion`: 지혜 Database·RAG

기능은 담당 feature 브랜치에서 개발하고 테스트한 뒤 `develop`을 대상으로 PR을 만든다. PR 제목은 한글로 작성한다.

## Shared contracts

`backend/app/schemas`, `legal_mcp/schemas`, `docs/최종 plan.md`, `docs/AI agent 명세서.md`의 공통 계약을 변경하기 전에 팀에 공유한다.

## Secrets

`.env`, API Key, DB 비밀번호, 개인정보를 commit하지 않는다.

팀 IP와 비밀값이 없는 접속 예시는 문서화할 수 있지만 비밀번호가 포함된 전체 DB URL은 commit하지 않는다.
