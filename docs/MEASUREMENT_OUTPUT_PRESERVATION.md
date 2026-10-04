# 시연·측정 결과 보존

시연·측정 명령을 다시 실행할 때는 매번 새로운 출력 경로를 지정한다. 기존 파일을 덮어쓰거나 이전 원본을 삭제하지 않는다.

```powershell
.venv/Scripts/python.exe -X utf8 scripts/portfolio_smoke.py --output output/portfolio/demo-run-01.json
.venv/Scripts/python.exe -X utf8 scripts/benchmark_analysis.py --repeats 1 --output-dir output/latency/demo-run-01
```

위 경로가 이미 존재하면 `demo-run-02` 같은 새 이름을 선택한다. `benchmark_analysis`는 기존 빈 폴더도 거절한다. 출력 폴더 또는 파일을 배타적으로 확보하므로 같은 경로의 동시 실행은 먼저 확보한 실행만 진행한다. 충돌한 실행은 종료 코드 2로 중단되며 API 요청, 캐시 냉각·예열, 하위 측정 프로세스를 실행하지 않는다.

새 시연 파일은 시작 시 빈 배열로 예약하고, 각 완료 시나리오의 성공·실패 결과를 즉시 갱신·flush한다. 반복 측정은 원본 파일과 요약의 파일 참조 구조를 유지한다. 중간에 실패한 새 실행은 기존 결과를 손상시키지 않으며 재시도도 새 경로를 사용한다. 이 변경은 프로세스 동시 실행의 출력 충돌 방지이며 갑작스러운 OS 종료에 대한 원자적 JSON 쓰기 보장은 추가하지 않는다.

회귀 테스트는 이전 파일의 바이트 보존, 충돌 시 외부 실행 금지, 빈 폴더 거절, 새 결과 및 실패 결과 저장, 두 동시 시연의 단일 실행을 확인한다. 실제 유료 모델 호출이나 기존 측정 데이터 갱신 없이 검증했다.
