# Frontend HTTP 연결 재사용

Backend 동기 요청이 매번 `httpx.request`로 클라이언트를 생성하던 경로를 프로세스 소유 연결 풀로 바꿨다. 초기화는 잠금으로 보호하며 정상 종료 시 `atexit`로 닫는다. HTTPX Client의 기본 연결 한도를 사용한다. SSE 수신과 모델 호출은 변경하지 않았다.

인증 헤더·Backend URL·타임아웃은 요청마다 전달한다. 공유 클라이언트에 사용자 인증 기본값을 설정하지 않으며 CookieJar 정책으로 응답 쿠키 저장을 거절한다. 응답 캐시나 자동 재시도를 추가하지 않았다. 종료 함수는 진행 중인 요청을 처리하는 정상 화면 흐름에서 호출하지 않는다. 강제 프로세스 종료 시 종료 콜백 실행은 보장되지 않는다.

## 검증

`frontend/tests/test_http_client_pool.py`는 동시 초기화 8개에서 단일 클라이언트 생성, 종료 및 재생성, 회원·게스트 64개 동시 요청의 헤더/쿠키 격리, 요청별 URL/타임아웃 변경을 검사한다. 실제 로컬 HTTP/1.1 서버에 네 요청을 보내 같은 TCP 연결 재사용과 사용자별 인증·쿠키 비전파를 확인한다. 기존 HTTP 오류·JSON 계약·POST 실패 동작 테스트도 유지한다.

## 실제 API 측정

원본: [frontend-http-pool.json](../output/portfolio/frontend-http-pool.json). 실행:

```powershell
$env:BACKEND_API_URL='http://127.0.0.1:8000'
.\.venv\Scripts\python.exe scripts/benchmark_frontend_http.py --output output/portfolio/frontend-http-pool-new.json
```

세 분야의 공개 카탈로그마다 준비 2쌍 이후 10쌍을 교대로 측정했다. 준비 포함 총 36쌍에서 응답 해시와 필드 계약이 일치했다. 기존 경로는 클라이언트 생성·종료를 포함하고 새 경로는 실제 `backend_client._request`를 사용한다.

| 분야 | 매번 생성 중앙값 | 풀 재사용 중앙값 |
|---|---:|---:|
| 주거 | 345.3927ms | 3.2125ms |
| 노동 | 392.9074ms | 3.4007ms |
| 소비자 | 362.3176ms | 3.3123ms |

로컬 공개 GET 단계 측정이며 전체 분석·검색·LLM 지연이나 운영 환경의 지연 개선 수치가 아니다. 측정 당시 작업 트리 코드 해시와 패키지 버전을 원본에 기록했다. 기존 출력 파일은 덮어쓰지 않는다. 인증 요청과 모델 호출은 0회다.

참고 계약: [HTTPX Client](https://www.python-httpx.org/api/#client)의 연결 풀·스레드 공유 지원과 [CookiePolicy](https://docs.python.org/3/library/http.cookiejar.html#http.cookiejar.CookiePolicy.set_ok)의 쿠키 수락 정책을 사용한다. 실제 저장되지 않는 동작은 설치된 HTTPX와 로컬 서버 테스트로 검증했다.
