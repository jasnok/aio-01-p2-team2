# 모델 비교 실험의 결과 보존

`compare_latency.py`는 새 출력 폴더를 배타적으로 확보하고, `compare_reranking.py`는 새 출력 파일을 배타적으로 연다. 기존 경로가 있으면 모델 호출 전에 CLI 종료 코드 2로 중단한다. 빈 기존 폴더도 거절하며 매 실행에 새 이름을 사용한다.

```powershell
.venv/Scripts/python.exe -X utf8 scripts/compare_latency.py --scope answer --scenarios 0 2 --variants baseline repair0 --max-calls 16 --output-dir output/latency/answer-run-01
.venv/Scripts/python.exe -X utf8 scripts/compare_reranking.py --model "평가할-모델-ID" --output output/phase3/reranking-run-01.json
```

명령은 실제 모델 호출을 실행하므로 여기서는 수행하지 않았다. 테스트는 합성 provider와 합성 결과만 사용했다.

비교 실험은 원본 JSON과 index.json 참조 구조를 유지한다. 리랭킹은 각 완료 사례의 결과를 갱신·flush하며 `pending_human_review`를 유지한다. 모델 순위는 사람 정답 라벨이 아니다. 입력 오류나 중간 실패 후 생성된 새 출력은 자동 삭제하지 않으며 재시도는 새 경로에서 실행한다. OS 종료에 대한 JSON 쓰기 원자성은 추가하지 않았다.

새 테스트 5개는 기존 바이트 보존, 출력 충돌 시 입력 조회·모델 초기화 전 중단, 정상 새 원본·인덱스·리랭킹 저장을 확인한다. 기존 시연 결과 보존 테스트를 포함한 관련 테스트 11개가 통과했다. 운영 모델 설정과 기존 측정 자료는 수정하지 않았다.
