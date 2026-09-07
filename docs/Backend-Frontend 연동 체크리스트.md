# Backend–Frontend Mock API 연동 체크리스트

이 문서는 `feature/backend-mock-api`의 FastAPI Mock API와 Streamlit Frontend를 연결할 때 사용한다. 체크가 모두 끝나기 전에는 Frontend Mock 데이터를 삭제하지 않는다.

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
