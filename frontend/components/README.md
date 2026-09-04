# Frontend components

예시 화면을 작은 표시 단위로 나눕니다.

- 입력: `question_form.py`
- 전체 결과 조립: `answer_view.py`
- 이후 분리: 상황 요약, 법령 카드, 판례 카드, 후속 질문, 결과 상태

컴포넌트는 Backend를 직접 호출하지 않고, 전달받은 검증된 View Model만 표시합니다.
