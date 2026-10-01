# 운영 로그의 상담 내용 노출 방지

## 문제와 변경

실행 결과 로그는 diagnostics 전체를 JSON으로 기록했다. 모델의 semantic_review 검토 사유, 인용 검증 오류 등 자유 텍스트가 함께 기록될 수 있었다. 또한 logger.exception은 외부 SDK·DB 예외 전문과 traceback을 남겨 상담 내용이나 연결 정보가 로그로 유입될 수 있었다.

Issue #106에서는 로그와 공개 응답의 계약을 분리했다. HTTP/SSE 결과와 diagnostics는 유지한다. 운영 메트릭은 허용한 필드의 유한한 0 이상 숫자만 기록한다. bool, 문자열, NaN, Infinity, 음수와 알 수 없는 필드는 제외한다.

- 총 시간 및 intake/retrieval/context/generation 시간
- 도구·모델 호출 수, 근거 수, 제외한 주장 수, 사용량을 모르는 호출 수
- input/output/total 토큰 수
- 고정된 intake/answer/answer_repair/verification/term 단계의 소요 시간
- 고정된 검색 도구의 소요 시간

개별 모델 호출 내용, 모델 이름, 검토 사유·이력, 원문 span, validation_error는 메트릭에 기록하지 않는다. 생성 상태는 스키마의 5개 값만 허용한다. 토큰 지표는 기존처럼 알려진 호출 사용량에 한정되며 실패 호출·embedding 비용 전체를 나타내지 않는다.

분석·검색·용어 생성·저장 실패 로그는 서버 실행 ID, 고정 단계, 예외 클래스 이름을 기록하고 예외 전문이나 traceback을 기록하지 않는다. 분석 이벤트에서 validation/retrieval/generation 단계를 추적하며 결과 저장 실패는 storage 단계다. 용어 실행 조회 자체가 실패하면 사용자 입력 경로 ID 대신 unavailable을 기록한다.

## 검증과 범위

합성 문자열 synthetic-private-marker를 모델 검토 사유, 지표의 잘못된 문자열, 예외 전문, 질문, 경로에 삽입하는 회귀 테스트를 추가했다. 허용한 숫자는 보존되고 원본 diagnostics는 변경되지 않으며, 실패 HTTP 오류 코드와 분석 종료 상태도 유지되는지 검사한다. 실제 모델 호출이나 실제 개인정보는 사용하지 않는다.

이 변경은 애플리케이션의 해당 운영 메트릭과 실패 로그에 한정한다. Docker/프록시 접근 로그, 외부 SDK 자체 로거, 관측 서비스의 설정과 보관 정책까지 검증한 것은 아니다. traceback을 제거하므로 운영 조사에는 실행 ID·단계·오류 유형과 통제된 재현 테스트를 함께 사용한다. 속도 향상 수치는 측정하지 않았으며 성능 개선으로 주장하지 않는다.
