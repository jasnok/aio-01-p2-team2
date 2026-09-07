# Backend–Frontend Mock API 연동 체크리스트

이 문서는 `feature/backend-mock-api`의 FastAPI Mock API와 Streamlit Frontend를 연결할 때 사용한다. 체크가 모두 끝나기 전에는 Frontend Mock 데이터를 삭제하지 않는다.

## 현재 검증 상태 — 2026-09-07

아래 항목은 Backend 테스트와 FastAPI TestClient로 제가 직접 확인했다.

- [x] Backend API 테스트와 계약 테스트: 13개 통과
- [x] 전체 프로젝트 테스트: 79개 통과
- [x] Health 응답: `is_mock=true`, `database=mock`, `redis=disabled`
- [x] Demo 회원·관리자 로그인, Bearer Token 인증, 관리자 FAQ 권한 차단
- [x] 공개/비밀 질문 열람 권한, 댓글 소유권, 댓글 알림, `Idempotency-Key`, 오류 Envelope
- [x] `/api/catalog/categories`, CORS preflight, 법률 분석·검색 Mock API 응답

아래 **사용자 확인 필요** 항목은 아직 체크하지 않았다. 현재 Streamlit Frontend는 기존 Mock 서비스만 사용하므로, 화면에서 Backend를 실제 호출하는 API 모드는 다음 Frontend 작업에서 연결해야 한다.

## 1. 실행 전

- [ ] Backend: `BACKEND_MOCK_MODE=true`로 실행한다. 예: `uvicorn backend.app.main:app --reload --port 8000`
- [ ] Frontend의 Backend Base URL이 `http://127.0.0.1:8000` 또는 팀 Backend IP/port를 가리킨다.
- [ ] Frontend가 MCP·PostgreSQL·Redis에 직접 요청하지 않고 Backend만 호출한다.
- [ ] `GET /health`가 200이고 `is_mock=true`, `database=mock`, `redis=disabled`를 표시한다.
- [ ] CORS 허용 Origin을 Streamlit 주소로 설정한다. 운영 배포에서 `*`는 사용하지 않는다.

## 2. 인증과 Header

- [ ] 회원가입 후 `session_token`을 Streamlit `st.session_state`에만 저장한다.
- [ ] 로그인 후 모든 회원 요청에 `Authorization: Bearer <session_token>`을 넣는다.
- [ ] 비회원 작성·조회 요청에는 Streamlit 세션별 UUID인 `X-Guest-Id`를 넣는다.
- [ ] 분석 생성 요청은 클릭마다 UUID `Idempotency-Key`를 만들고, 재시도에는 **같은 키**를 사용한다.
- [ ] 로그·화면·파일에 Session Token, 비밀번호, Password Hash를 표시하지 않는다.
- [ ] Demo 회원 `user@lawpath.demo / Demo1234!`, 관리자 `admin@lawpath.demo / Admin1234!` 로그인에 성공한다.

## 3. 법률 분석과 검색

- [ ] `POST /api/legal/questions`의 category와 response Evidence 모델이 Frontend `LegalQuestionView`와 맞는다.
- [ ] 같은 `Idempotency-Key`로 두 번 보내도 이력·알림이 중복 생성되지 않는다.
- [ ] `X-Mock-Scenario: success`, `no_results`, `no_evidence`, `mcp_error` 화면 처리가 확인된다.
- [ ] 법령·판례 검색 결과가 없을 때 오류 화면 대신 빈 배열 안내를 표시한다.

## 4. FAQ·질문·댓글

- [ ] `/api/faqs`는 고정 FAQ를 pinned 우선, display_order 순서로 표시한다.
- [ ] 질문 생성 기본 visibility가 `PRIVATE`다.
- [ ] 공개글은 누구나 본문과 댓글을 조회·작성할 수 있다.
- [ ] 비밀글은 작성자와 관리자만 본문·댓글을 조회·작성할 수 있다.
- [ ] 목록에서는 공개·비밀글 모두 제목만큼은 표시된다.
- [ ] 검색은 공개글 제목·본문, 비밀글 제목만 대상으로 한다.
- [ ] 비회원 질문·댓글의 수정/삭제에서 비밀번호를 다시 입력하고, Backend가 원문 대신 Hash만 보관한다.
- [ ] 회원 질문·댓글의 수정/삭제는 로그인 Session 소유권으로 확인한다.
- [ ] 관리자는 타인 댓글 삭제만 가능하며 수정은 불가능하다.
- [ ] 질문 목록은 `PENDING` 우선, 이후 최신순이며 page_size 기본 10/최대 50이다.

## 5. 이력·알림·오류

- [ ] 비회원은 자신의 guest_id 이력만, 회원은 자신의 계정 이력만 본다.
- [ ] 질문·댓글·분석 이벤트 후 알림이 생성되고, 미읽음 우선 최신순이다.
- [ ] 비밀글 알림에 질문 본문이나 댓글 원문이 포함되지 않는다.
- [ ] 401/403/404/409/422 응답이 `detail.code`, `message`, `request_id`, `field_errors` Envelope인지 확인한다.
- [ ] Backend 재시작 후 메모리 데이터가 초기화되는 Mock 단계 제약을 화면 또는 README에 안내한다.

## 6. 전환 완료 기준

- [ ] Frontend API 모드로 위 항목을 모두 통과했다.
- [ ] `python -m pytest backend/tests -v`와 Frontend 테스트가 통과한다.
- [ ] 담당자 둘이 대표 흐름(비회원 비밀글, 회원 공개글, 관리자 답변/댓글 삭제)을 함께 확인했다.
- [ ] 이 시점에만 Frontend Mock 데이터 제거 PR을 별도로 만든다.

## 7. 사용자 확인 필요 — 쉬운 실행 순서

### Backend만 먼저 확인하기

1. PowerShell에서 프로젝트 폴더로 이동한다.

   ```powershell
   cd C:\aio-01-p2-team2
   uvicorn backend.app.main:app --reload --port 8000
   ```

2. 브라우저에서 `http://127.0.0.1:8000/docs`를 연다. 이것은 Backend API를 버튼으로 시험하는 화면이다.
3. `GET /health`의 **Try it out → Execute**를 눌러 `200`과 `is_mock: true`를 확인한다.
4. `POST /api/auth/login`에서 아래 Demo 회원으로 로그인한다.

   ```json
   {"email":"user@lawpath.demo","password":"Demo1234!"}
   ```

5. 응답의 `session_token`은 잠깐만 복사해 `GET /api/auth/me` 요청 Header의 `Authorization: Bearer 토큰값`으로 넣는다. 화면 캡처·메신저·문서에는 토큰을 남기지 않는다.
6. `POST /api/questions`에 `X-Guest-Id: test-guest-001` Header와 질문 JSON을 넣어 비밀글을 하나 만든다. 다른 `X-Guest-Id`로 상세 조회했을 때 `403 FORBIDDEN`이면 정상이다.
7. 같은 과정을 `visibility: "PUBLIC"`으로 반복한다. 다른 Guest ID도 본문과 댓글을 볼 수 있으면 정상이다.

### Frontend와 실제로 연결됐는지 확인하기

현재는 이 단계가 **미완료**다. Frontend가 `mock_auth_service.py`, `mock_community_service.py` 대신 `frontend/clients/backend_client.py`를 사용하도록 API 모드를 구현한 뒤 아래를 수행한다.

1. Frontend 환경변수의 Backend 주소를 `http://127.0.0.1:8000`으로 설정한다.
2. Streamlit을 실행하고 로그인·질문 등록·댓글 작성·알림 조회를 각각 한 번 수행한다.
3. 동시에 Backend 터미널에 해당 HTTP 요청이 찍히는지 확인한다.
4. 브라우저 개발자 도구가 아닌 화면 기준으로도, Backend를 중지했을 때 “Backend 연결 불가” 오류가 보이면 Frontend가 Mock이 아닌 Backend를 호출하는 것이다.
5. 다시 Backend를 켠 뒤 비회원 비밀글, 회원 공개글, 관리자 답변·타인 댓글 삭제의 세 흐름을 담당자 둘이 함께 확인한다.
