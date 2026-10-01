# 2차 최적화 구현·검증 기록

작업일: 2026-10-01. 브랜치: `codex/portfolio-optimize-v2`. 기준: 1차 PR [#83](https://github.com/jasnok/aio-01-p2-team2/pull/83)의 `main` 병합 커밋 `68dfe9c`.

## 우선순위별 작업

### 1. 관련성 평가를 위한 기준과 도구

자연어 질문 15건에 대해 검색 방식과 순위를 숨긴 [원문 검토표](../output/optimization/relevance-review.html)를 만들었습니다. 기존·가중합·RRF의 후보 문서와 서로 다른 청크를 함께 표시합니다. 검토자가 0~3점의 관련성 등급을 선택하고 JSON으로 저장·다시 불러올 수 있습니다. HTML을 로컬 브라우저에서 직접 열어 사용하며 서버가 필요하지 않습니다.

관련성 정의는 0 무관, 1 주제만 유사, 2 질문 일부의 근거, 3 핵심 질문의 직접 근거입니다. 같은 문서의 청크가 여러 개면 가장 낮은 등급을 선택하는 보수적인 후보 통합 평가입니다. 따라서 산출값은 문서 순위의 Precision@3·후보 통합 nDCG@3이며 청크 선택 차이, 전체 DB Recall, 법률 정답률을 측정하지 않습니다.

아직 사람의 채점은 없으며 품질 수치를 만들지 않았습니다. 검토한 자료의 해시가 다른 JSON은 평가에서 거부하고 미검토 질문은 평균에서 제외합니다. 임계값·RRF 기본값 변경이나 의미 기반 재평가 모델 도입은 관련성 검토 후 결정합니다.

```powershell
.venv/Scripts/python -X utf8 scripts/review_retrieval.py
# 검토표에서 저장한 JSON을 아래 --labels 위치로 복사한 뒤 실행
.venv/Scripts/python -X utf8 scripts/review_retrieval.py --labels output/optimization/relevance-labels.json
```

### 2. 검색 병렬화와 답변용 근거 압축

서로 독립적인 분야별 검색 2~3개를 동시에 실행합니다. 완료 순서대로 진행 이벤트를 보내지만 최종 근거 순서는 기존 분야별 순서를 유지하고 중복을 제거합니다. 검색 하나가 실패하면 나머지 작업을 취소하고 종료를 기다립니다. Redis 저장 콜백은 직렬화합니다. 도구별 소요 시간도 기록합니다.

답변용 입력은 자료 유형을 우선 보존하고 검색 점수·원래 순서를 사용해 최대 6개 문서를 선택합니다. 각 문서에서 질문의 문자 쌍과 겹치는 원문 구절 최대 3개를 추출하며 각 구절은 280자 이하입니다. 새 의미 기반 재평가 모델은 도입하지 않았습니다. 화면·PDF에 반환되는 검색 원문은 그대로 유지합니다. 추출은 결정적이지만 잘린 문장이나 예외 규정을 놓칠 수 있어 의미 관련성·법적 타당성의 수동 검토가 필요합니다.

### 3. 인용 구절 번호 선택

모델은 원문을 복사하는 대신 제공된 구절 번호를 선택합니다. 서버가 원문과 근거 ID를 붙이고, 표시 답변도 인용을 가진 주장의 텍스트로 구성합니다. 존재하지 않는 구절 번호는 대체 답변으로 처리합니다. 구절 존재 검사를 주장과 원문의 의미 일치 검사로 해석하지 않습니다.

기본값은 `CITATION_MODE=spans`입니다. 1차 방식과 비교하려면 `quotes`를 사용하고 Backend 컨테이너를 재생성합니다. 이전 실행 결과의 재조회·PDF 출력 계약도 유지합니다.

### 4. 대기 화면 개선

검색이 끝나는 대로 자료 제목과 원문 일부를 먼저 표시합니다. 이때 답변 작성과 인용 확인이 진행 중임을 안내하고, 생성 단계 메시지를 검색과 구분합니다. SSE 재연결로 같은 자료가 다시 와도 중복 표시하지 않습니다.

### 5. 반복 검색 비용과 빌드 개선

동일 질의의 동시 임베딩 요청은 한 호출을 공유합니다. 검색 결과는 프로세스별 최대 128개·60초 TTL 캐시를 사용하며 질문·분야·자료 유형·top-k·모델·DB·검색 설정·데이터 버전별로 분리합니다. 반환값은 깊은 복사로 보호하고 오류는 캐시하지 않습니다. 답변이나 개인 대화 이력은 캐시하지 않습니다. 공유 Redis 캐시는 아니므로 프로세스 재시작 시 비워집니다.

`RETRIEVAL_CACHE_TTL_SECONDS=0`이면 검색 결과 캐시를 끕니다. 자료를 갱신할 때 `RETRIEVAL_DATASET_REVISION`을 함께 변경하고 MCP 컨테이너를 재생성합니다. 변경 전 캐시는 최대 TTL 동안 남을 수 있습니다. 임베딩 캐시는 128개·5분을 유지합니다.

실행 의존성과 개발 의존성은 이미 분리되어 있어 유지했습니다. Docker 빌드 대상에서 테스트·문서를 제외했습니다. 의존성 설치 레이어는 재사용되는 것을 확인했으며 이미지 크기 감소율은 별도로 측정하지 않았습니다.

## 검증 결과

회귀 테스트 271개 통과, 기존 실서버 통합 테스트 4개 제외. 실제 API 4건은 일반 질문 3건 모두 LLM 답변과 원문 인용 검사를 통과하고, 정보 부족 질문 1건은 보완 안내로 종료했습니다. 중복 요청·소유자 분리·SSE 재조회·중간 자료 이벤트·인용문 존재·답변과 인용 주장 일치도 확인했습니다. 브라우저에서 소비자 답변·주장별 원문과 PDF 다운로드를 확인했습니다.

| 같은 합성 질문의 단일 실행 | 1차 | 2차 | 2차 상태 |
|---|---:|---:|---|
| 주거 | 32.187초 | 24.063초 | LLM 답변 |
| 근로 | 38.079초 | 26.812초 | LLM 답변 |
| 소비자 | 116.188초 | 19.188초 | LLM 답변 |
| 정보 부족 | 12.437초 | 8.328초 | 보완 안내 |

모델 출력·캐시 상태·서버 부하가 통제되지 않은 단일 실행 비교입니다. 1차 소비자는 인용 검사 실패 대체 답변이었습니다. 개선률·p95·법률 정답률을 확정하지 않습니다. 답변 생성 입력 토큰은 주거 1,406→846, 근로 2,434→1,439였으며 intake·임베딩 비용은 이 토큰 수에 포함하지 않습니다.

실제 MCP를 사용하는 캐시 예열 후 순차·병렬 각 3회 비교에서 근거가 같았습니다. 중앙값은 주거 60→46ms, 근로 67→66ms, 소비자 85→70ms입니다. API·LLM 전체 응답 시간이 아닙니다.

별도 동일 프로세스의 검색 결과 캐시 비교에서는 임베딩을 미리 예열했고, 캐시가 없는 첫 검색은 주거 75.554ms·근로 49.202ms·소비자 325.185ms, 캐시된 반복 검색은 0.048~0.150ms였습니다. MCP 네트워크·입력 판단·답변 생성은 포함하지 않습니다.

## 결과와 재현

- [실제 API 결과](../output/optimization/after-smoke.json)
- [1차·2차 비교](../output/optimization/comparison.json)
- [검색 병렬화 비교](../output/optimization/runtime-benchmark.json)
- [검색 결과 캐시 비교](../output/optimization/cache-benchmark.json)
- [중간 검색 자료 화면](../output/optimization/early-evidence.png)
- [최종 소비자 답변 화면](../output/optimization/demo-result.png)

```powershell
./scripts/test_all.ps1
.venv/Scripts/python -X utf8 scripts/portfolio_smoke.py --require-llm --output output/optimization/after-smoke.json
.venv/Scripts/python -X utf8 scripts/summarize_optimization.py
```

병렬 검색 비교는 Backend 컨테이너에 `scripts/`와 `output/optimization/baseline_runtime.py`를 복사하고 `python scripts/benchmark_runtime.py --baseline /app/baseline_runtime.py --output /app/runtime-benchmark.json`을 실행합니다. 캐시 비교는 MCP 컨테이너에 `scripts/`를 복사하고 `python scripts/benchmark_retrieval_cache.py --output /app/cache-benchmark.json`을 실행합니다. 두 스크립트는 답변 생성 LLM을 호출하지 않지만 검색 질의 임베딩 비용이 발생할 수 있습니다.

다음 품질 결정은 15건의 원문 관련성 채점과 압축 구절의 의미·예외 조건 검토입니다. 아직 없는 사람 평가를 자동 생성해 정답으로 취급하지 않았습니다.
