# Backend–Legal MCP 계약

## 확정 Tool

| Tool | 입력 | 출력 |
|---|---|---|
| `search_laws` | `query`, `category`, `top_k<=3` | 법령 Evidence 목록 |
| `search_cases` | `query`, `category`, `top_k<=3` | 판례 Evidence 목록 |
| `get_law_article` | `law_name`, `article_number` | Evidence 또는 `null` |

모든 Tool은 `ToolResult`를 사용합니다.

```text
success, tool, data, error_code, message
```

검색 성공 후 결과가 없으면 오류가 아니라 `success=true`, `data=[]`입니다. 검색 점수는 관련도이며 승소 가능성이 아닙니다.
