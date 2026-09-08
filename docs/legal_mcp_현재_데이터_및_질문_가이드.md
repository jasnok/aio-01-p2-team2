# Legal MCP 현재 데이터 및 질문 가이드

## 현재 DB에서 활용 가능한 데이터

현재 Legal MCP는 PostgreSQL에서 법령과 소비자 상담 사례를 읽어 검색할 수 있다.

```text
법령 데이터
- 소비자: 전자상거래 소비자보호, 소비자기본법, 약관 관련 법령
- 주거: 민법, 주택임대차보호법, 주택임대차보호법 시행령
- 노동: 근로기준법, 근로자퇴직급여 보장법

상담 사례
- consumer 카테고리: 678건

판례
- CASE 데이터: 현재 없음
```

## Tool별 현재 사용 가능 범위

| Tool | 현재 상태 | 질문 예시 |
| --- | --- | --- |
| `search_laws` | 사용 가능 | “퇴직금 관련 법령 찾아줘”, “주택임대차보호법 관련 내용을 찾아줘”, “온라인 쇼핑 환불 관련 법률은?” |
| `search_consultations` | 사용 가능 | “온라인 쇼핑몰이 환불을 거부해요”, “카드 결제를 취소하고 싶어요”, “사업자가 폐업했는데 환불받을 수 있나요?” |
| `search_legal_documents` | 사용 가능 | “전세보증금 반환과 관련된 법령 찾아줘”, “퇴직금 관련 법령을 찾아줘”, “소비자 환불 관련 법령을 찾아줘” |
| `search_cases` | 호출 가능, 결과 없음 | CASE 데이터가 적재되면 유사 판례 검색 가능 |
| `get_case_detail` | 현재 실사용 불가 | 판례 검색 결과의 `document_id`가 필요하지만 현재 CASE 데이터가 없음 |
| `get_law_article` | 제한적 | 법령명과 조문 번호가 모두 적재되어야 하며, 현재 법령 문서의 `article_number`는 비어 있을 수 있음 |

## 현재 가장 활용하기 좋은 기능

```text
소비자 상담 사례 검색
→ search_consultations

주거·노동·소비자 법령 검색
→ search_laws / search_legal_documents
```

## 데이터 적재 후 확장되는 기능

다음 데이터가 추가되면 현재 구현된 Tool을 더 폭넓게 활용할 수 있다.

- `CASE` 문서, 청크, 임베딩 적재
  - `search_cases`
  - `get_case_detail`
- 법령 조문 단위 문서와 `article_number` 적재
  - `get_law_article`
