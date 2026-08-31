# Frontend → Backend → MCP 연결 확인

이 기능은 병훈 Food MCP의 교육용 Mock 데이터로 세 서버의 통신만 확인합니다. 법률 기능이나 실제 법률 데이터와는 분리되어 있습니다.

## 환경변수

Backend `backend/.env`:

```env
FOOD_MCP_URL=http://192.100.200.72:8011/mcp
ENABLE_INTEGRATION_DEBUG=true
MCP_REQUEST_TIMEOUT_SECONDS=15
```

Frontend `frontend/.env`:

```env
BACKEND_API_URL=http://192.100.200.195:8000
FRONTEND_REQUEST_TIMEOUT_SECONDS=30
```

## 실행 순서

1. 병훈 PC에서 Food MCP를 `192.100.200.72:8011/mcp`로 실행한다.
2. 다혁 PC에서 Backend를 실행한다.
3. 상옥 PC에서 Frontend를 실행한다.

```powershell
backend\.venv\Scripts\python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
frontend\.venv\Scripts\python -m streamlit run frontend\app.py
```

## Backend 직접 확인

```powershell
Invoke-RestMethod http://192.100.200.195:8000/api/integration/mcp
```

`search_restaurants`, `get_restaurant_detail`이 반환되면 Backend → MCP 연결이 정상이다.

```powershell
$body = @{
    region = "서울"
    food_category = "한식"
    max_price = 20000
    allergy = "없음"
    limit = 3
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri "http://192.100.200.195:8000/api/integration/mcp/food-search" `
  -ContentType "application/json; charset=utf-8" `
  -Body $body
```

`source=food-restaurant-catalog`과 음식점 Mock 데이터가 반환되면 Tool 실행이 정상이다.

## Frontend 확인

1. `http://192.100.200.232:8501`에 접속한다.
2. 사이드바의 `Frontend → Backend → MCP 확인`을 펼친다.
3. `MCP Tool 목록 확인`을 누른다.
4. `서울 한식 Mock 검색`을 누른다.
5. `Frontend → Backend → MCP 연결 성공`과 음식점 카드가 표시되는지 확인한다.

테스트가 끝난 후 확인 기능을 숨기려면 Backend에서 다음과 같이 변경한다.

```env
ENABLE_INTEGRATION_DEBUG=false
```
